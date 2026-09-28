"""
RoadEye Backend Server
Flask + Flask-Sock WebSocket server providing:
  GET  /api/status              — health + model info
  POST /api/video/start         — start processing (source: webcam/espcam/upload)
  POST /api/video/stop          — stop processing
  POST /api/video/upload        — upload file for processing
  GET  /stream/video            — MJPEG annotated stream
  WS   /ws/telemetry            — WebSocket telemetry push
"""
import sys
import os

# Disable OpenCV multithreading and set FFmpeg threading limits to prevent libavcodec crashes
os.environ["OPENCV_FFMPEG_THREAD_ONCE"] = "1"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "threads|1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# Ensure backend directory is in path for sibling imports
sys.path.insert(0, os.path.dirname(__file__))

import io
import json
import time
import datetime
from collections import Counter
import logging
import threading
import traceback
from pathlib import Path

import cv2
cv2.setNumThreads(0)

import numpy as np
from flask import Flask, request, jsonify, Response, send_from_directory, send_file
from flask_cors import CORS
from flask_sock import Sock

import config as cfg
from models_loader import load_all_models
from pipeline import RoadEyePipeline, InferenceResult

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("roadeye.server")

# ─── Operational Event Recording ──────────────────────────────────────────────
LOGS_DIR = cfg.BACKEND_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
OPERATIONS_LOG_FILE = LOGS_DIR / "operations.log"
_recent_logs: list[str] = [
    f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [System] RoadEye Level-3 ADAS Stack Online.",
    f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [Perception] Loaded C++ ONNX Models.",
    f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [Fusion] EKF fusion filter initialized."
]
_logs_lock = threading.Lock()

def _append_operation_log(msg: str) -> str:
    timestamp_str = datetime.datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp_str}] {msg}"
    with _logs_lock:
        _recent_logs.append(formatted)
        if len(_recent_logs) > 500:
            _recent_logs.pop(0)
    try:
        with open(OPERATIONS_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass
    return formatted

# ─── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
CORS(app, origins=cfg.ALLOWED_ORIGINS)
sock = Sock(app)

# ─── Global State ─────────────────────────────────────────────────────────────
_models = {}
_pipeline: RoadEyePipeline | None = None

_capture_lock = threading.Lock()
_capture: cv2.VideoCapture | None = None
_source_type: str = "none"       # "webcam" | "espcam" | "upload"
_source_path: str = ""           # file path or URL

_running = threading.Event()
_latest_frame: np.ndarray | None = None
_latest_result: InferenceResult | None = None
_latest_jpeg: bytes | None = None
_frame_lock = threading.Lock()

_overlay_toggles = {
    "showBoxes":    True,
    "showDrivable": True,
    "showLanes":    True,
    "showDepth":    False,
}

# WebSocket client list
_ws_clients: set = set()
_ws_lock = threading.Lock()

# ─── Model Loading (done at startup) ─────────────────────────────────────────
def _init_models():
    global _models, _pipeline
    log.info("Loading perception models…")
    _models = load_all_models()
    _pipeline = RoadEyePipeline(_models)
    log.info("Pipeline ready.")


# ─── Video Capture Thread ─────────────────────────────────────────────────────
def _capture_loop():
    global _latest_frame, _latest_result, _latest_jpeg, _capture

    log.info("Capture loop started (source=%s)", _source_type)

    while _running.is_set():
        with _capture_lock:
            cap = _capture

        if cap is None or not cap.isOpened():
            time.sleep(0.1)
            continue

        # Real-time frame dropping logic to keep up with video playback rate
        if _source_type == "upload":
            video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            if not hasattr(_capture_loop, "start_time") or not hasattr(_capture_loop, "source") or _capture_loop.source != _source_path:
                _capture_loop.start_time = time.perf_counter()
                _capture_loop.source = _source_path
                _capture_loop.last_frame_idx = 0

            elapsed = time.perf_counter() - _capture_loop.start_time
            target_frame = int(elapsed * video_fps)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames > 0 and target_frame >= total_frames:
                # Reset video looping by re-opening capture cleanly under lock
                _capture_loop.start_time = time.perf_counter()
                target_frame = 0
                with _capture_lock:
                    if _capture is not None:
                        _capture.release()
                    _capture = _open_capture("upload", _source_path)
                    cap = _capture
                _capture_loop.last_frame_idx = 0

            # Discard frames that we need to skip using fast cap.grab()
            skip_count = target_frame - _capture_loop.last_frame_idx - 1
            if skip_count > 0:
                actual_skip = min(skip_count, 30) # cap to prevent lockups
                for _ in range(actual_skip):
                    cap.grab()
                _capture_loop.last_frame_idx += actual_skip

            ret, frame = cap.read()
            if ret:
                _capture_loop.last_frame_idx += 1
            else:
                # Restart if reading fails at end of stream by re-opening capture cleanly under lock
                _capture_loop.start_time = time.perf_counter()
                with _capture_lock:
                    if _capture is not None:
                        _capture.release()
                    _capture = _open_capture("upload", _source_path)
                    cap = _capture
                _capture_loop.last_frame_idx = 0
                ret, frame = cap.read()
                if ret:
                    _capture_loop.last_frame_idx = 1
        else:
            # For live webcam/espcam sources, clear OpenCV buffer to get latest live frame
            if _source_type in ["webcam", "espcam"]:
                for _ in range(4): # typically buffer size is 5
                    cap.grab()
            ret, frame = cap.read()

        if not ret:
            time.sleep(0.05)
            continue

        # Run perception pipeline
        try:
            annotated, result = _pipeline.run(
                frame,
                show_boxes   = _overlay_toggles.get("showBoxes",    True),
                show_seg     = _overlay_toggles.get("showDrivable",  True),
                show_depth   = _overlay_toggles.get("showDepth",    False),
                show_lanes   = _overlay_toggles.get("showLanes",    True),
            )
        except Exception:
            log.error("Pipeline error:\n" + traceback.format_exc())
            annotated = frame
            result = InferenceResult()

        # Encode to JPEG for MJPEG stream
        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            continue

        with _frame_lock:
            _latest_frame  = annotated
            _latest_result = result
            _latest_jpeg   = buf.tobytes()

        # Push telemetry to all WebSocket clients
        _broadcast_telemetry(result)

        # Target ~25 FPS
        time.sleep(0.02)


# ─── WebSocket Broadcast ──────────────────────────────────────────────────────
def _broadcast_telemetry(result: InferenceResult):
    now = time.time()
    last_state = getattr(_broadcast_telemetry, "_last_state", {
        "time": 0.0, "summary": "", "warn_time": 0.0, "pothole_time": 0.0, "hb_time": 0.0
    })

    det_items = [
        {"label": d.label, "conf": round(float(d.conf), 2)}
        for d in result.detections
    ]
    pothole_items = [
        {"label": d.label, "conf": round(float(d.conf), 2)}
        for d in result.potholes
    ]

    new_logs = []
    if det_items:
        counts = Counter(d["label"] for d in det_items)
        summary_str = ", ".join(f"{c} {l}" for l, c in counts.items())
        if summary_str != last_state.get("summary") or (now - last_state.get("time", 0)) > 2.0:
            msg = f"[Perception] Tracked {len(det_items)} target(s): {summary_str}"
            new_logs.append(_append_operation_log(msg))
            last_state["summary"] = summary_str
            last_state["time"] = now

    if pothole_items and (now - last_state.get("pothole_time", 0)) > 2.5:
        msg = f"[Perception] ⚠️ Road Anomaly: {len(pothole_items)} Pothole(s) detected in path"
        new_logs.append(_append_operation_log(msg))
        last_state["pothole_time"] = now

    if result.warnings and (now - last_state.get("warn_time", 0)) > 2.0:
        for w in result.warnings:
            new_logs.append(_append_operation_log(f"[Safety Alert] {w}"))
        last_state["warn_time"] = now

    if _source_type != "none" and (now - last_state.get("hb_time", 0)) > 4.0:
        msg = f"[Telemetry] Source: {_source_type.upper()} | FPS: {result.fps:.1f} | Collision Risk: {result.risk_score:.0f}%"
        new_logs.append(_append_operation_log(msg))
        last_state["hb_time"] = now

    _broadcast_telemetry._last_state = last_state

    payload = json.dumps({
        "riskScore":       result.risk_score,
        "closestDistM":    result.closest_dist_m,
        "detections":      len(result.detections),
        "potholes":        len(result.potholes),
        "detection_items": det_items,
        "pothole_items":   pothole_items,
        "fps":             result.fps,
        "mode":            result.mode,
        "warnings":        result.warnings,
        "source":          _source_type,
        "ts":              now,
        "logs":            new_logs,
    })
    dead = set()
    with _ws_lock:
        clients = list(_ws_clients)
    for ws in clients:
        try:
            ws.send(payload)
        except Exception:
            dead.add(ws)
    if dead:
        with _ws_lock:
            _ws_clients.difference_update(dead)


# ─── Helper: open a capture ───────────────────────────────────────────────────
def _open_capture(source_type: str, path_or_url: str) -> cv2.VideoCapture:
    if source_type == "webcam":
        cap = cv2.VideoCapture(cfg.WEBCAM_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
    elif source_type == "espcam":
        url = path_or_url or cfg.ESPCAM_URL
        cap = cv2.VideoCapture(url)
    elif source_type == "upload":
        cap = cv2.VideoCapture(path_or_url)
    else:
        raise ValueError(f"Unknown source type: {source_type}")

    if not cap.isOpened():
        raise RuntimeError(f"Could not open capture: {source_type} / {path_or_url}")
    return cap


# ══════════════════════════════════════════════════════════════════════════════
#   REST API Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/status", methods=["GET"])
def api_status():
    model_info = {k: {"backend": v.backend, "stub": v.stub}
                  for k, v in _models.items()}
    with _frame_lock:
        res = _latest_result
    return jsonify({
        "status":    "online",
        "running":   _running.is_set(),
        "source":    _source_type,
        "models":    model_info,
        "fps":       res.fps if res else 0,
        "riskScore": res.risk_score if res else 0,
    })


@app.route("/api/video/start", methods=["POST"])
def api_start():
    global _capture, _source_type, _source_path

    if _running.is_set():
        return jsonify({"error": "Already running"}), 400

    data = request.get_json(silent=True) or {}
    source_type  = data.get("source", "webcam")
    path_or_url  = data.get("url", "")

    try:
        cap = _open_capture(source_type, path_or_url)
    except Exception as e:
        log.error(f"Cannot open capture: {e}")
        return jsonify({"error": str(e)}), 500

    with _capture_lock:
        _capture     = cap
        _source_type = source_type
        _source_path = path_or_url

    _running.set()
    t = threading.Thread(target=_capture_loop, daemon=True, name="capture-loop")
    t.start()

    _append_operation_log(f"[Video] Pipeline started - source: {source_type.upper()}")
    log.info("Video processing started: source=%s", source_type)
    return jsonify({"status": "started", "source": source_type})


@app.route("/api/video/stop", methods=["POST"])
def api_stop():
    global _capture, _source_type

    _running.clear()
    time.sleep(0.15)

    with _capture_lock:
        if _capture:
            _capture.release()
            _capture = None
        _source_type = "none"

    _append_operation_log("[Video] Pipeline stopped by operator")
    log.info("Video processing stopped.")
    return jsonify({"status": "stopped"})


@app.route("/api/video/upload", methods=["POST"])
def api_upload():
    global _capture, _source_type, _source_path

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    save_path = cfg.UPLOAD_FOLDER / f.filename
    f.save(str(save_path))
    log.info("Uploaded video saved: %s", save_path)
    _append_operation_log(f"[Upload] Video uploaded: {f.filename}")

    # Stop existing capture if any
    if _running.is_set():
        _running.clear()
        time.sleep(0.15)
        with _capture_lock:
            if _capture:
                _capture.release()
                _capture = None

    try:
        cap = _open_capture("upload", str(save_path))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    with _capture_lock:
        _capture     = cap
        _source_type = "upload"
        _source_path = str(save_path)

    _running.set()
    t = threading.Thread(target=_capture_loop, daemon=True, name="capture-loop-upload")
    t.start()

    _append_operation_log(f"[Video] Pipeline started - source: UPLOAD ({f.filename})")
    return jsonify({"status": "started", "source": "upload", "filename": f.filename})


@app.route("/api/logs", methods=["GET"])
def api_get_logs():
    limit = request.args.get("limit", default=100, type=int)
    with _logs_lock:
        logs_slice = _recent_logs[-limit:]
    return jsonify({"logs": logs_slice, "total": len(_recent_logs)})


@app.route("/api/logs/download", methods=["GET"])
def api_download_logs():
    if not OPERATIONS_LOG_FILE.exists():
        OPERATIONS_LOG_FILE.touch()
    return send_file(
        str(OPERATIONS_LOG_FILE),
        as_attachment=True,
        download_name=f"roadeye_operations_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        mimetype="text/plain"
    )


@app.route("/api/overlays", methods=["POST"])
def api_overlays():
    global _overlay_toggles
    data = request.get_json(silent=True) or {}
    _overlay_toggles.update({k: v for k, v in data.items()
                              if k in _overlay_toggles})
    return jsonify({"overlays": _overlay_toggles})


@app.route("/api/config/espcam", methods=["POST"])
def api_set_espcam():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    cfg.ESPCAM_URL = url
    return jsonify({"espcam_url": url})


# ─── MJPEG Stream ────────────────────────────────────────────────────────────
def _mjpeg_generator():
    boundary = b"--RoadEyeFrame\r\n"
    header_tpl = (
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: %d\r\n\r\n"
    )

    # Placeholder frame when pipeline isn't running
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank, "RoadEye — Waiting for Video Source",
                (60, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 229, 255), 2)
    cv2.putText(blank, "Select source from dashboard to begin",
                (110, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120, 120, 120), 1)
    _, blank_buf = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 75])
    blank_bytes = blank_buf.tobytes()

    last_sent = None
    while True:
        with _frame_lock:
            frame_bytes = _latest_jpeg

        if frame_bytes is None:
            frame_bytes = blank_bytes

        if frame_bytes is not last_sent:
            last_sent = frame_bytes
            yield (boundary
                   + header_tpl % len(frame_bytes)
                   + frame_bytes
                   + b"\r\n")
        time.sleep(0.033)   # ~30 FPS limit on stream


@app.route("/stream/video")
def stream_video():
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=RoadEyeFrame",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ─── WebSocket Telemetry ──────────────────────────────────────────────────────
@sock.route("/ws/telemetry")
def ws_telemetry(ws):
    log.info("WebSocket client connected")
    with _ws_lock:
        _ws_clients.add(ws)
    try:
        # Send immediate snapshot
        with _frame_lock:
            res = _latest_result
        with _logs_lock:
            init_logs = list(_recent_logs[-35:])
        ws.send(json.dumps({
            "riskScore":    res.risk_score if res else 0,
            "closestDistM": res.closest_dist_m if res else 0,
            "detections":   len(res.detections) if res else 0,
            "potholes":     len(res.potholes) if res else 0,
            "fps":          res.fps if res else 0,
            "mode":         res.mode if res else "ACTIVE",
            "warnings":     res.warnings if res else [],
            "source":       _source_type,
            "ts":           time.time(),
            "logs":         init_logs,
        }))
        # Keep connection alive — data is pushed from _broadcast_telemetry
        while True:
            try:
                msg = ws.receive(timeout=30)
                if msg:
                    # Handle overlay toggle messages from dashboard
                    try:
                        data = json.loads(msg)
                        if "overlays" in data:
                            _overlay_toggles.update(data["overlays"])
                    except Exception:
                        pass
            except Exception:
                break
    except Exception:
        pass
    finally:
        with _ws_lock:
            _ws_clients.discard(ws)
# ─── Root Redirect ────────────────────────────────────────────────────────────
@app.route("/")
def index_redirect():
    from flask import redirect
    return redirect("http://localhost:5173/")


# ─── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 60)
    log.info(" RoadEye ADAS Backend — starting up")
    log.info("=" * 60)

    _init_models()
    for init_msg in _recent_logs:
        try:
            with open(OPERATIONS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(init_msg + "\n")
        except Exception:
            pass

    log.info("Server listening on http://%s:%d", cfg.HOST, cfg.PORT)
    log.info("MJPEG stream: http://localhost:%d/stream/video", cfg.PORT)
    log.info("WebSocket:    ws://localhost:%d/ws/telemetry", cfg.PORT)

    # Use threaded=True so WebSocket + MJPEG can coexist
    app.run(host=cfg.HOST, port=cfg.PORT, threaded=True, use_reloader=False)
