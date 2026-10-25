"""
RoadEye Model Loader
Attempts to load ONNX models via onnxruntime, then PyTorch, then flags simulation.
Gracefully degrades when models are Git LFS stubs or packages are missing.
"""
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any

import numpy as np
from config import (
    MODEL_PATHS, PT_MODEL_PATHS, is_lfs_stub,
    DETECTION_CLASSES, POTHOLE_CLASSES
)

log = logging.getLogger("roadeye.models")


# ─── Try to import optional inference backends ────────────────────────────────
try:
    import onnxruntime as ort
    ORT_AVAILABLE = True
    log.info("onnxruntime available — ONNX inference enabled.")
except ImportError:
    ORT_AVAILABLE = False
    log.warning("onnxruntime not installed — ONNX inference disabled.")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# ─── Model Descriptor ─────────────────────────────────────────────────────────
@dataclass
class ModelInfo:
    name: str
    backend: str          # "onnx" | "torch" | "simulation"
    session: Any = None   # ort.InferenceSession or torch Module
    input_name: str = ""
    output_names: list = field(default_factory=list)
    stub: bool = False


def _load_onnx(path: Path, name: str) -> Optional[ModelInfo]:
    if not ORT_AVAILABLE:
        return None
    if is_lfs_stub(path):
        log.warning(f"[{name}] ONNX file is a Git LFS stub — skipping ONNX load.")
        return None
    try:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        
        # Optimize ONNX runtime options for Raspberry Pi 5 quad-core ARM layout
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 4
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        sess = ort.InferenceSession(str(path), sess_options=sess_options, providers=providers)
        input_name  = sess.get_inputs()[0].name
        output_names = [o.name for o in sess.get_outputs()]
        log.info(f"[{name}] ✅ Loaded ONNX model from {path}")
        return ModelInfo(name=name, backend="onnx", session=sess,
                         input_name=input_name, output_names=output_names)
    except Exception as e:
        log.error(f"[{name}] ONNX load failed: {e}")
        return None


def _load_torch(path: Path, name: str) -> Optional[ModelInfo]:
    if not TORCH_AVAILABLE:
        return None
    if is_lfs_stub(path):
        log.warning(f"[{name}] PT file is a Git LFS stub — skipping torch load.")
        return None
    try:
        ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
        # Try ultralytics YOLO first
        try:
            from ultralytics import YOLO
            model = YOLO(str(path))
            log.info(f"[{name}] ✅ Loaded via Ultralytics YOLO from {path}")
            return ModelInfo(name=name, backend="torch_ultralytics", session=model)
        except Exception:
            pass
        log.error(f"[{name}] torch load succeeded but no compatible runner found.")
        return None
    except Exception as e:
        log.error(f"[{name}] torch load failed: {e}")
        return None


def load_all_models() -> dict[str, ModelInfo]:
    """Load all perception models. Falls back to simulation if weights unavailable."""
    models: dict[str, ModelInfo] = {}

    for key in ["detection", "segmentation", "pothole", "depth"]:
        onnx_path = MODEL_PATHS[key]
        pt_path   = PT_MODEL_PATHS[key]

        info = _load_onnx(onnx_path, key) or _load_torch(pt_path, key)

        if info is None:
            log.warning(f"[{key}] No real model available — using SIMULATION mode.")
            info = ModelInfo(name=key, backend="simulation", stub=True)

        models[key] = info

    return models


# ─── ONNX Preprocessing / Postprocessing helpers ──────────────────────────────
def letterbox(im: np.ndarray, new_shape: tuple = (640, 640), color: tuple = (114, 114, 114)) -> tuple[np.ndarray, float, tuple[float, float]]:
    """Resize and pad image while meeting stride-multiple constraints."""
    import cv2
    shape = im.shape[:2]  # current shape [height, width]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2

    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im, r, (dw, dh)


def preprocess_frame(frame_bgr: np.ndarray, target_hw: tuple = (640, 640), normalize: bool = True, use_letterbox: bool = False):
    """
    BGR numpy HWC -> float32 NCHW tensor ready for ONNX/torch inference.
    If normalize=True, scales to [0, 1].
    If use_letterbox=True, returns (tensor, (r, (dw, dh))).
    Otherwise returns tensor.
    """
    import cv2
    if use_letterbox:
        im, r, dwdh = letterbox(frame_bgr, target_hw)
        rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32)
        if normalize:
            rgb /= 255.0
        tensor = rgb.transpose(2, 0, 1)[np.newaxis, ...]
        return tensor, (r, dwdh)

    h, w = target_hw
    resized = cv2.resize(frame_bgr, (w, h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
    if normalize:
        rgb /= 255.0
    tensor = rgb.transpose(2, 0, 1)[np.newaxis, ...]
    return tensor


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45) -> list[int]:
    """Pure-numpy Non-Maximum Suppression (NMS). Returns surviving indices."""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        ix1 = np.maximum(x1[i], x1[order[1:]])
        iy1 = np.maximum(y1[i], y1[order[1:]])
        ix2 = np.minimum(x2[i], x2[order[1:]])
        iy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, ix2 - ix1) * np.maximum(0.0, iy2 - iy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thresh]
    return keep


def filter_containment(detections: list[dict], threshold: float = 0.70) -> list[dict]:
    """If one detection is substantially inside another, keep only the higher-confidence detection."""
    if len(detections) <= 1:
        return detections
    surviving = []
    for i, d1 in enumerate(detections):
        b1 = d1["box"]
        area1 = max(1, (b1[2] - b1[0]) * (b1[3] - b1[1]))
        suppress = False
        for j, d2 in enumerate(detections):
            if i == j:
                continue
            b2 = d2["box"]
            ix1 = max(b1[0], b2[0]); iy1 = max(b1[1], b2[1])
            ix2 = min(b1[2], b2[2]); iy2 = min(b1[3], b2[3])
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2 - ix1) * (iy2 - iy1)
                # If d1 is mostly contained inside d2 and d1 has lower confidence
                if (inter / area1 > threshold) and (d1["conf"] <= d2["conf"]):
                    suppress = True
                    break
        if not suppress:
            surviving.append(d1)
    return surviving


def decode_yolo_detect_output(output: np.ndarray,
                               orig_hw: tuple,
                               conf_thresh: float = 0.40,
                               iou_thresh: float = 0.45,
                               letterbox_meta: tuple | None = None,
                               target_classes: list[int] | None = None) -> list[dict]:
    """
    Decode YOLO detection output.
    Handles both NMS-baked shape [1,N,6] and raw head [1,C,8400].
    Supports letterbox unscaling and class-selective decoding.
    Returns list of {"box":[x1,y1,x2,y2], "conf":float, "cls":int}.
    """
    out = output[0]           # remove batch dim → shape (N,6) or (C,8400)
    oh, ow = orig_hw

    # NMS-baked case: shape (max_det, 6)
    if out.ndim == 2 and out.shape[1] == 6:
        results = []
        for row in out:
            x1, y1, x2, y2, conf, cls = row
            if conf < conf_thresh:
                continue
            c_id = int(cls)
            if target_classes is not None and c_id not in target_classes:
                continue
            if letterbox_meta is not None:
                r, (dw, dh) = letterbox_meta
                x1 = np.clip((x1 - dw) / r, 0, ow)
                y1 = np.clip((y1 - dh) / r, 0, oh)
                x2 = np.clip((x2 - dw) / r, 0, ow)
                y2 = np.clip((y2 - dh) / r, 0, oh)
            else:
                x1 = np.clip(x1 / 640 * ow, 0, ow)
                y1 = np.clip(y1 / 640 * oh, 0, oh)
                x2 = np.clip(x2 / 640 * ow, 0, ow)
                y2 = np.clip(y2 / 640 * oh, 0, oh)
            results.append({"box": [int(x1), int(y1), int(x2), int(y2)], "conf": float(conf), "cls": c_id})
        return filter_containment(results)

    # Raw head case: shape (C, 8400) where C = 4+num_classes
    if out.ndim == 2 and out.shape[1] == 8400:
        C = out.shape[0]
        num_cls = C - 4
        boxes_xywh = out[:4].T        # (8400, 4) cx, cy, w, h
        cls_scores  = out[4:].T       # (8400, num_cls)

        results = []
        classes_to_check = target_classes if target_classes is not None else list(range(num_cls))
        
        for c_id in classes_to_check:
            if c_id >= num_cls:
                continue
            scores = cls_scores[:, c_id]
            mask = scores >= conf_thresh
            if not np.any(mask):
                continue
            c_boxes = boxes_xywh[mask]
            c_scores = scores[mask]
            
            # xywh -> xyxy in 640 coordinates
            bx, by, bw, bh = c_boxes[:, 0], c_boxes[:, 1], c_boxes[:, 2], c_boxes[:, 3]
            x1 = bx - bw / 2
            y1 = by - bh / 2
            x2 = bx + bw / 2
            y2 = by + bh / 2
            
            # Unscale from letterbox or standard resize
            if letterbox_meta is not None:
                r, (dw, dh) = letterbox_meta
                x1 = np.clip((x1 - dw) / r, 0, ow)
                y1 = np.clip((y1 - dh) / r, 0, oh)
                x2 = np.clip((x2 - dw) / r, 0, ow)
                y2 = np.clip((y2 - dh) / r, 0, oh)
            else:
                x1 = np.clip(x1 / 640 * ow, 0, ow)
                y1 = np.clip(y1 / 640 * oh, 0, oh)
                x2 = np.clip(x2 / 640 * ow, 0, ow)
                y2 = np.clip(y2 / 640 * oh, 0, oh)
                
            xyxy = np.stack([x1, y1, x2, y2], axis=1)
            
            # Dimension & aspect ratio sanity filters
            bw_real = xyxy[:, 2] - xyxy[:, 0]
            bh_real = xyxy[:, 3] - xyxy[:, 1]
            valid = (bw_real >= 14) & (bh_real >= 8) & (bw_real / np.maximum(bh_real, 1) < 5.0) & (bw_real / np.maximum(bh_real, 1) > 0.2)
            xyxy = xyxy[valid]
            c_scores = c_scores[valid]
            
            if len(xyxy) == 0:
                continue
                
            keep = nms(xyxy, c_scores, iou_thresh)
            for ki in keep:
                results.append({
                    "box": [int(xyxy[ki, 0]), int(xyxy[ki, 1]), int(xyxy[ki, 2]), int(xyxy[ki, 3])],
                    "conf": float(c_scores[ki]),
                    "cls": int(c_id)
                })
        return filter_containment(results)

    return []
