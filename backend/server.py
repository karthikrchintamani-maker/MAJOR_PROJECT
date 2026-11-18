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
os.environ["OPENCV_FFMPEG_THREADS"] = "1"
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
import socket
import zlib
from collections import Counter, deque
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
_capture_thread: threading.Thread | None = None
_camera_reader_thread: threading.Thread | None = None
_latest_raw_camera_frame: np.ndarray | None = None
_latest_raw_camera_lock = threading.Lock()
_source_type: str = "none"       # "webcam" | "espcam" | "upload"
_source_path: str = ""           # file path or URL

_running = threading.Event()
_latest_frame: np.ndarray | None = None
_latest_result: InferenceResult | None = None
_latest_jpeg: bytes | None = None
_frame_lock = threading.Lock()


def _stop_capture_thread():
    """Safely and deterministically stop any active capture thread and release hardware."""
    global _capture_thread, _camera_reader_thread, _capture, _source_type
    _running.clear()
    if _camera_reader_thread is not None and _camera_reader_thread.is_alive():
        if _camera_reader_thread != threading.current_thread():
            _camera_reader_thread.join(timeout=2.0)
        _camera_reader_thread = None
    if _capture_thread is not None and _capture_thread.is_alive():
        if _capture_thread != threading.current_thread():
            _capture_thread.join(timeout=3.0)
        _capture_thread = None
    with _latest_raw_camera_lock:
        global _latest_raw_camera_frame
        _latest_raw_camera_frame = None
    with _capture_lock:
        if _capture is not None:
            try:
                _capture.release()
            except Exception as e:
                log.warning(f"Error releasing capture: {e}")
            _capture = None
        _source_type = "none"
    # Essential pause for Windows DirectShow driver to cleanly detach hardware
    time.sleep(0.35)

_overlay_toggles = {
    "showBoxes":    True,
    "showDrivable": True,
    "showLanes":    True,
    "showDepth":    False,
}

# WebSocket client list
_ws_clients: set = set()
_ws_lock = threading.Lock()

# ─── Mobile IoT UDP Receiver (Kotlin App on Port 5005) ────────────────────────
_mobile_iot_lock = threading.Lock()
_latest_mobile_iot: dict | None = None
_mobile_iot_stats = {
    "total_packets": 0,
    "dropped_packets": 0,
    "last_seq": None,
    "rate_hz": 0.0,
    "last_received": 0.0,
    "crc_errors": 0,
    "sender_addr": None,
    "device_id": None,
    "_last_logged_connect": 0.0,
}
_mobile_packet_times = deque(maxlen=100)
_udp_socket: socket.socket | None = None
_udp_running = threading.Event()
_udp_thread: threading.Thread | None = None
_beacon_thread: threading.Thread | None = None

def _udp_telemetry_loop():
    """Continuously listens for JSON UDP datagrams from the Kotlin mobile app on port 5005."""
    global _udp_socket, _latest_mobile_iot
    log.info("Starting Mobile IoT UDP receiver on 0.0.0.0:5005 (RoadEye Nexus)...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 5005))
        sock.settimeout(1.0)
        _udp_socket = sock
    except Exception as e:
        log.error(f"Failed to bind UDP port 5005: {e}")
        return

    while _udp_running.is_set():
        try:
            data, addr = sock.recvfrom(16384)
        except socket.timeout:
            continue
        except Exception as e:
            if not _udp_running.is_set():
                break
            log.warning(f"UDP recv error: {e}")
            time.sleep(0.1)
            continue

        now = time.time()
        _mobile_packet_times.append(now)
        while _mobile_packet_times and now - _mobile_packet_times[0] > 2.0:
            _mobile_packet_times.popleft()
        rate_hz = len(_mobile_packet_times) / 2.0 if _mobile_packet_times else 0.0

        try:
            pkt = json.loads(data.decode("utf-8"))
        except Exception:
            continue

        # CRC32 verification (zlib.crc32 over compact JSON without "crc32" key)
        received_crc = pkt.pop("crc32", None)
        crc_match = False
        if received_crc:
            try:
                compact_bytes = json.dumps(pkt, separators=(',', ':')).encode('utf-8')
                calc_crc = f"{zlib.crc32(compact_bytes) & 0xFFFFFFFF:08X}"
                crc_match = (received_crc == calc_crc)
            except Exception:
                pass
        pkt["crc32"] = received_crc
        pkt["crc_match"] = crc_match

        seq = pkt.get("seq")
        with _mobile_iot_lock:
            _latest_mobile_iot = pkt
            stats = _mobile_iot_stats
            stats["total_packets"] += 1
            stats["last_received"] = now
            stats["rate_hz"] = round(rate_hz, 1)
            stats["sender_addr"] = f"{addr[0]}:{addr[1]}"
            stats["device_id"] = pkt.get("device_id", "Mobile_Node")
            if not crc_match and received_crc:
                stats["crc_errors"] += 1
            if isinstance(seq, int):
                last_s = stats["last_seq"]
                if last_s is not None and seq > last_s + 1:
                    stats["dropped_packets"] += (seq - last_s - 1)
                stats["last_seq"] = seq

        if stats["total_packets"] == 1 or (now - stats.get("_last_logged_connect", 0.0)) > 60.0:
            dev = pkt.get("device_id", "Mobile_Node")
            _append_operation_log(f"[IoT Mobile] Live telemetry node active: {dev} ({addr[0]}:{addr[1]})")
            stats["_last_logged_connect"] = now

        if pkt.get("road_intelligence", {}).get("impact_detected"):
            vib = pkt.get("road_intelligence", {}).get("vibration_rms", 0.0)
            _append_operation_log(f"[Road Anomaly] ⚠️ High-Impact Shock detected by Mobile Sensor: {vib:.3f} m/s²")

    try:
        sock.close()
    except Exception:
        pass
    log.info("Mobile IoT UDP receiver exited.")

def _start_udp_receiver():
    global _udp_thread
    if _udp_thread is None or not _udp_thread.is_alive():
        _udp_running.set()
        _udp_thread = threading.Thread(target=_udp_telemetry_loop, daemon=True, name="mobile-udp-receiver")
        _udp_thread.start()

def _telemetry_beacon_loop():
    """Broadcasts WebSocket telemetry at 10 Hz when the video pipeline is idle."""
    while True:
        try:
            if not _running.is_set():
                _broadcast_telemetry(None)
            time.sleep(0.1)
        except Exception:
            time.sleep(0.5)

def _start_telemetry_beacon():
    global _beacon_thread
    if _beacon_thread is None or not _beacon_thread.is_alive():
        _beacon_thread = threading.Thread(target=_telemetry_beacon_loop, daemon=True, name="ws-telemetry-beacon")
        _beacon_thread.start()

# ─── Model Loading (done at startup) ─────────────────────────────────────────
def _init_models():
    global _models, _pipeline
    log.info("Loading perception models…")
    _models = load_all_models()
    _pipeline = RoadEyePipeline(_models)
    log.info("Pipeline ready.")


# ─── Camera Background Reader (Zero Latency Buffer Drain) ─────────────────────
def _camera_reader_loop():
    """Continuously drains the physical camera buffer at native 30 FPS to guarantee 0ms latency."""
    global _latest_raw_camera_frame
    log.info("Camera background reader thread started.")
    while _running.is_set():
        with _capture_lock:
            cap = _capture
        if cap is None or not cap.isOpened():
            time.sleep(0.01)
            continue
        ret, frame = cap.read()
        if ret and frame is not None:
            with _latest_raw_camera_lock:
                _latest_raw_camera_frame = frame
        else:
            time.sleep(0.005)
    log.info("Camera background reader thread exited.")


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
                # Reset video looping cleanly via seek without tearing down FFmpeg contexts
                _capture_loop.start_time = time.perf_counter()
                target_frame = 0
                _capture_loop.last_frame_idx = 0
                with _capture_lock:
                    if cap is not None and cap.isOpened():
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            # Discard frames that we need to skip using fast cap.grab()
            skip_count = target_frame - _capture_loop.last_frame_idx - 1
            if skip_count > 0:
                actual_skip = min(skip_count, 15)  # conservative skip to avoid decoder pipeline starvation
                for _ in range(actual_skip):
                    if not _running.is_set():
                        break
                    with _capture_lock:
                        if cap is None or not cap.isOpened():
                            break
                        if not cap.grab():
                            break
                _capture_loop.last_frame_idx += actual_skip

            if not _running.is_set():
                break

            with _capture_lock:
                if cap is None or not cap.isOpened():
                    break
                ret, frame = cap.read()

            if ret:
                _capture_loop.last_frame_idx += 1
            else:
                # Seek back to frame 0 for smooth continuous playback
                _capture_loop.start_time = time.perf_counter()
                _capture_loop.last_frame_idx = 0
                with _capture_lock:
                    if cap is not None and cap.isOpened():
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if ret:
                            _capture_loop.last_frame_idx = 1
        else:
            if not _running.is_set():
                break

            frame = None
            if _camera_reader_thread is not None and _camera_reader_thread.is_alive():
                with _latest_raw_camera_lock:
                    if _latest_raw_camera_frame is not None:
                        frame = _latest_raw_camera_frame
                        _latest_raw_camera_frame = None
                if frame is None:
                    time.sleep(0.005)
                    continue
                ret = True
            else:
                with _capture_lock:
                    if cap is None or not cap.isOpened():
                        break
                    ret, frame = cap.read()

        if not ret or frame is None:
            time.sleep(0.04)
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
def _broadcast_telemetry(result: InferenceResult | None = None):
    if result is None:
        with _frame_lock:
            result = _latest_result or InferenceResult()

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

    # Fetch latest Mobile IoT telemetry
    with _mobile_iot_lock:
        mobile_data = _latest_mobile_iot
        mobile_stats = dict(_mobile_iot_stats)

    is_mobile_active = (now - mobile_stats.get("last_received", 0.0)) < 3.5

    payload = json.dumps({
        "riskScore":          result.risk_score,
        "closestDistM":       result.closest_dist_m,
        "detections":         len(result.detections),
        "potholes":           len(result.potholes),
        "detection_items":    det_items,
        "pothole_items":      pothole_items,
        "fps":                result.fps,
        "mode":               result.mode,
        "warnings":           result.warnings,
        "source":             _source_type,
        "ts":                 now,
        "logs":               new_logs,
        # Mobile Kotlin IoT telemetry
        "mobileIot":          mobile_data,
        "mobileIotActive":    is_mobile_active,
        "mobileIotHz":        mobile_stats.get("rate_hz", 0.0),
        "mobileIotStats":     mobile_stats,
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
def _open_capture(source_type: str, path_or_url: str, camera_index: int = None) -> cv2.VideoCapture:
    if source_type == "webcam":
        cam_idx = int(camera_index) if camera_index is not None else cfg.WEBCAM_INDEX
        log.info(f"Opening webcam index {cam_idx} (requested: {camera_index})")

        # Try DirectShow first (preserves physical camera index ordering on Windows)
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            log.warning(f"CAP_DSHOW failed for index {cam_idx}, trying MSMF")
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
        if not cap.isOpened():
            log.warning(f"CAP_MSMF failed for index {cam_idx}, trying default backend")
            cap = cv2.VideoCapture(cam_idx)

        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera device at index {cam_idx}. Check USB connection and privacy permissions.")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Test read and warm up camera sensor to ensure auto-exposure/gain stabilize
        test_frame = None
        for _ in range(5):
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                break
            time.sleep(0.1)

        if not ret or test_frame is None:
            cap.release()
            raise RuntimeError(f"Camera index {cam_idx} opened but cannot read video frames.")

        cfg.WEBCAM_INDEX = cam_idx
        log.info(f"Successfully opened and verified webcam index {cam_idx} ({test_frame.shape[1]}x{test_frame.shape[0]})")
    elif source_type == "espcam":
        url = path_or_url or cfg.ESPCAM_URL
        cap = cv2.VideoCapture(url)
    elif source_type == "upload":
        p = Path(path_or_url)
        if not p.is_file():
            p = cfg.UPLOAD_FOLDER / path_or_url
        cap = cv2.VideoCapture(str(p))
    else:
        raise ValueError(f"Unknown source type: {source_type}")

    if not cap.isOpened():
        raise RuntimeError(f"Could not open capture: {source_type} (index: {camera_index if camera_index is not None else cfg.WEBCAM_INDEX}) / {path_or_url}")
    return cap


# ══════════════════════════════════════════════════════════════════════════════
#   REST API Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/cameras", methods=["GET"])
def api_get_cameras():
    """Detect all available cameras and friendly names without locking device handles."""
    cameras = []
    try:
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        devices = graph.get_input_devices()
        for idx, name in enumerate(devices):
            clean_name = name.strip()
            # Distinguish external USB from built-in laptop camera clearly
            if "usb" in clean_name.lower():
                tag = "External USB WebCam"
            elif "hd" in clean_name.lower() or "integrated" in clean_name.lower():
                tag = "Built-in Laptop Camera"
            else:
                tag = f"Camera {idx}"
            cameras.append({
                "index": idx,
                "name": clean_name,
                "label": f"{clean_name} (Index {idx}) — {tag}",
                "tag": tag
            })
    except Exception as e:
        log.warning(f"pygrabber discovery failed, falling back to pnputil/opencv: {e}")

    if not cameras:
        # Fallback to pnputil + OpenCV probe
        names = []
        try:
            import subprocess
            res = subprocess.run(["pnputil", "/enum-devices", "/class", "Camera"], capture_output=True, text=True, timeout=3)
            for line in res.stdout.splitlines():
                if "Device Description:" in line:
                    names.append(line.split(":", 1)[1].strip())
        except Exception:
            pass

        for idx in range(3):
            name = names[idx] if idx < len(names) else f"Camera {idx}"
            tag = "External USB WebCam" if "usb" in name.lower() else "Built-in Laptop Camera"
            cameras.append({
                "index": idx,
                "name": name,
                "label": f"{name} (Index {idx}) — {tag}",
                "tag": tag
            })

    if not cameras:
        cameras.append({"index": 0, "name": "Default Webcam", "label": "Default Webcam (Index 0)"})

    return jsonify({
        "cameras": cameras,
        "default_index": cfg.WEBCAM_INDEX
    })


@app.route("/api/status", methods=["GET"])
def api_status():
    model_info = {k: {"backend": v.backend, "stub": v.stub}
                  for k, v in _models.items()}
    with _frame_lock:
        res = _latest_result
    with _mobile_iot_lock:
        m_stats = dict(_mobile_iot_stats)
    now = time.time()
    return jsonify({
        "status":             "online",
        "running":            _running.is_set(),
        "source":             _source_type,
        "webcam_index":       cfg.WEBCAM_INDEX,
        "models":             model_info,
        "fps":                res.fps if res else 0,
        "riskScore":          res.risk_score if res else 0,
        "mobile_iot_active":  (now - m_stats.get("last_received", 0.0)) < 3.5,
        "mobile_iot_device":  m_stats.get("device_id"),
        "mobile_iot_hz":      m_stats.get("rate_hz", 0),
        "mobile_iot_packets": m_stats.get("total_packets", 0),
    })


@app.route("/api/iot/telemetry", methods=["GET"])
def api_get_iot_telemetry():
    """Returns the latest mobile IoT telemetry packet received on UDP port 5005."""
    with _mobile_iot_lock:
        pkt = _latest_mobile_iot
        stats = dict(_mobile_iot_stats)
    now = time.time()
    active = (now - stats.get("last_received", 0.0)) < 3.5
    return jsonify({
        "active": active,
        "stats": stats,
        "data": pkt
    })


@app.route("/api/iot/simulate", methods=["POST"])
def api_simulate_iot():
    """Allows injecting or testing an incoming Kotlin UDP datagram."""
    data = request.get_json(silent=True) or {}
    now = time.time()
    sample_pkt = {
        "device_id": data.get("device_id", "RoadEye_Nexus_Node01"),
        "seq": int(data.get("seq", int(now * 10) % 100000)),
        "timestamp": now,
        "stream_hz": 20,
        "thermal_status": "NOMINAL",
        "sensors": {
            "accel": data.get("accel", {"x": 0.12, "y": 9.81, "z": -0.45}),
            "gyro": data.get("gyro", {"x": 0.01, "y": -0.02, "z": 0.05}),
            "mag": {"x": 25.1, "y": -12.3, "z": 45.0},
            "gravity": {"x": 0.05, "y": 9.80, "z": 0.11},
            "linear_accel": {"x": 0.22, "y": -0.14, "z": 0.85},
            "rotation_vector": {"x": 0.012, "y": -0.008, "z": 0.707, "w": 0.707},
            "orientation": data.get("orientation", {"pitch_deg": 1.5, "roll_deg": -0.8, "yaw_deg": 182.4}),
            "barometer": {"pressure_hpa": 910.25, "rel_altitude_m": 895.4},
            "ambient_light": {"lux": 1240.5, "condition": "DAYLIGHT"},
            "proximity": {"distance_cm": 5.0, "is_near": False},
            "audio": {"active": True, "rms_dbfs": -34.2, "peak_amp": 0.125, "zcr_hz": 420.5},
            "gps": data.get("gps", {
                "lat": 13.134,
                "lng": 77.962,
                "altitude_m": 920.0,
                "speed_mps": 14.5,
                "bearing": 182.4,
                "accuracy_m": 4.2,
                "has_fix": True
            }),
            "availability": {
                "accel": True, "gyro": True, "mag": True, "gravity": True,
                "linear_accel": True, "rotation_vector": True, "barometer": True,
                "light": True, "proximity": True, "audio": True
            }
        },
        "device_health": {
            "battery_pct": 82,
            "battery_temp_c": 33.4,
            "charging": True,
            "wifi_rssi_dbm": -54,
            "wifi_link_mbps": 433
        },
        "road_intelligence": data.get("road_intelligence", {
            "condition_score": 88,
            "surface_class": "SMOOTH",
            "vibration_rms": 0.885,
            "impact_detected": False
        }),
        "obd2": data.get("obd2", {
            "connected": True,
            "protocol": "ISO 15765-4 (CAN 11/500)",
            "speed_kmh": 52,
            "rpm": 2400,
            "throttle_pos": 18.5,
            "coolant_temp_c": 88,
            "engine_load": 34.2,
            "intake_temp_c": 29,
            "maf_gps": 14.25,
            "timing_advance_deg": 12.5,
            "fuel_level_pct": 68.0,
            "dtc_count": 0,
            "dtcs": []
        }),
    }

    # Calculate CRC32
    compact_bytes = json.dumps(sample_pkt, separators=(',', ':')).encode('utf-8')
    calc_crc = f"{zlib.crc32(compact_bytes) & 0xFFFFFFFF:08X}"
    sample_pkt["crc32"] = calc_crc
    sample_pkt["crc_match"] = True

    with _mobile_iot_lock:
        global _latest_mobile_iot
        _latest_mobile_iot = sample_pkt
        _mobile_iot_stats["total_packets"] += 1
        _mobile_iot_stats["last_received"] = now
        _mobile_iot_stats["rate_hz"] = 20.0
        _mobile_iot_stats["sender_addr"] = "127.0.0.1:local_sim"
        _mobile_iot_stats["device_id"] = sample_pkt["device_id"]

    return jsonify({"status": "simulated", "crc32": calc_crc, "data": sample_pkt})


@app.route("/api/video/start", methods=["POST"])
def api_start():
    global _capture, _source_type, _source_path, _capture_thread

    data = request.get_json(silent=True) or {}
    source_type  = data.get("source", "webcam")
    path_or_url  = data.get("url", "")
    camera_index = data.get("camera_index", None)

    # Cleanly stop any existing capture thread
    _stop_capture_thread()

    try:
        cap = _open_capture(source_type, path_or_url, camera_index)
    except Exception as e:
        log.error(f"Cannot open capture: {e}")
        return jsonify({"error": str(e)}), 500

    with _capture_lock:
        _capture     = cap
        _source_type = source_type
        _source_path = path_or_url

    _running.set()
    if source_type in ("webcam", "espcam"):
        with _latest_raw_camera_lock:
            _latest_raw_camera_frame = None
        _camera_reader_thread = threading.Thread(target=_camera_reader_loop, daemon=True, name="camera-reader")
        _camera_reader_thread.start()
    _capture_thread = threading.Thread(target=_capture_loop, daemon=True, name="capture-loop")
    _capture_thread.start()

    cam_log_str = f" (Index: {camera_index})" if source_type == "webcam" and camera_index is not None else ""
    _append_operation_log(f"[Video] Pipeline started - source: {source_type.upper()}{cam_log_str}")
    log.info("Video processing started: source=%s%s", source_type, cam_log_str)
    return jsonify({"status": "started", "source": source_type, "webcam_index": cfg.WEBCAM_INDEX})


@app.route("/api/video/stop", methods=["POST"])
def api_stop():
    _stop_capture_thread()
    _append_operation_log("[Video] Pipeline stopped by operator")
    log.info("Video processing stopped.")
    return jsonify({"status": "stopped"})


@app.route("/api/video/upload", methods=["POST"])
def api_upload():
    global _capture, _source_type, _source_path, _capture_thread

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    save_path = cfg.UPLOAD_FOLDER / f.filename
    f.save(str(save_path))
    log.info("Uploaded video saved: %s", save_path)
    _append_operation_log(f"[Upload] Video uploaded: {f.filename}")

    # Deterministically stop existing capture before opening new upload
    _stop_capture_thread()

    try:
        cap = _open_capture("upload", str(save_path))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    with _capture_lock:
        _capture     = cap
        _source_type = "upload"
        _source_path = str(save_path)

    _running.set()
    _capture_thread = threading.Thread(target=_capture_loop, daemon=True, name="capture-loop-upload")
    _capture_thread.start()

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
    boundary = b"--frame"

    # Placeholder frame when pipeline isn't running or first frame pending
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank, "RoadEye Perception Engine Active",
                (60, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 229, 255), 2)
    cv2.putText(blank, "Awaiting video frames...",
                (140, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 140, 140), 1)
    _, blank_buf = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 75])
    blank_bytes = blank_buf.tobytes()

    last_sent = None
    last_sent_time = 0.0

    try:
        while True:
            with _frame_lock:
                frame_bytes = _latest_jpeg

            current_data = frame_bytes if frame_bytes is not None else blank_bytes
            now = time.time()

            # Deliver immediately if new frame arrived or every 0.8s as keep-alive
            if current_data is not last_sent or (now - last_sent_time) >= 0.8:
                header = (
                    boundary + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(current_data)).encode() + b"\r\n\r\n"
                )
                yield header + current_data + b"\r\n"
                last_sent = current_data
                last_sent_time = now

            time.sleep(0.02)
    except (GeneratorExit, BrokenPipeError, ConnectionResetError):
        pass


@app.route("/stream/video")
def stream_video():
    resp = Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@app.route("/api/video/frame", methods=["GET"])
def api_latest_frame():
    with _frame_lock:
        data = _latest_jpeg
    if data is None:
        return Response(status=204)
    resp = Response(data, mimetype="image/jpeg")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


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
        with _mobile_iot_lock:
            mobile_data = _latest_mobile_iot
            mobile_stats = dict(_mobile_iot_stats)
        ws.send(json.dumps({
            "riskScore":       res.risk_score if res else 0,
            "closestDistM":    res.closest_dist_m if res else 0,
            "detections":      len(res.detections) if res else 0,
            "potholes":        len(res.potholes) if res else 0,
            "fps":             res.fps if res else 0,
            "mode":            res.mode if res else "ACTIVE",
            "warnings":        res.warnings if res else [],
            "source":          _source_type,
            "ts":              time.time(),
            "logs":            init_logs,
            "mobileIot":       mobile_data,
            "mobileIotActive": (time.time() - mobile_stats.get("last_received", 0.0)) < 3.5,
            "mobileIotHz":     mobile_stats.get("rate_hz", 0.0),
            "mobileIotStats":  mobile_stats,
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
    import argparse
    parser = argparse.ArgumentParser(description="RoadEye ADAS Backend Server")
    parser.add_argument("--host", default=cfg.HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=cfg.PORT, help="Port to bind to (default 5001)")
    args = parser.parse_args()

    host = args.host
    port = args.port

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

    log.info("Server listening on http://%s:%d", host, port)
    log.info("MJPEG stream: http://localhost:%d/stream/video", port)
    log.info("WebSocket:    ws://localhost:%d/ws/telemetry", port)
    log.info("UDP Port:     0.0.0.0:5005 (Kotlin Mobile Telemetry Receiver)")

    # Start background threads for Mobile IoT UDP listener and WebSocket telemetry beacon
    _start_udp_receiver()
    _start_telemetry_beacon()

    # Use threaded=True so WebSocket + MJPEG can coexist
    app.run(host=host, port=port, threaded=True, use_reloader=False)
