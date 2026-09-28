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
def preprocess_frame(frame_bgr: np.ndarray, target_hw: tuple = (640, 640)) -> np.ndarray:
    """
    BGR numpy HWC → float32 NCHW [0,1] tensor ready for ONNX/torch inference.
    Returns shape (1, 3, H, W).
    """
    import cv2
    h, w = target_hw
    resized = cv2.resize(frame_bgr, (w, h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    tensor = rgb.astype(np.float32) / 255.0
    tensor = tensor.transpose(2, 0, 1)[np.newaxis, ...]   # NCHW
    return tensor


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45) -> list[int]:
    """Simple pure-numpy NMS. Returns surviving indices."""
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
        inter = np.maximum(0, ix2 - ix1) * np.maximum(0, iy2 - iy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thresh]
    return keep


def decode_yolo_detect_output(output: np.ndarray,
                               orig_hw: tuple,
                               conf_thresh: float = 0.40,
                               iou_thresh: float = 0.45) -> list[dict]:
    """
    Decode YOLO detection output.
    Handles both NMS-baked shape [1,N,6] and raw head [1,C,8400].
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
            # Rescale from 640 → original
            x1 = int(x1 / 640 * ow); y1 = int(y1 / 640 * oh)
            x2 = int(x2 / 640 * ow); y2 = int(y2 / 640 * oh)
            results.append({"box": [x1, y1, x2, y2], "conf": float(conf), "cls": int(cls)})
        return results

    # Raw head case: shape (C, 8400) where C = 4+num_classes
    if out.ndim == 2 and out.shape[1] == 8400:
        C = out.shape[0]
        num_cls = C - 4
        boxes_xywh = out[:4].T        # (8400, 4)
        cls_scores  = out[4:].T        # (8400, num_cls)
        conf_scores = cls_scores.max(axis=1)
        cls_ids     = cls_scores.argmax(axis=1)

        mask = conf_scores >= conf_thresh
        boxes_xywh = boxes_xywh[mask]
        conf_scores = conf_scores[mask]
        cls_ids = cls_ids[mask]

        if len(boxes_xywh) == 0:
            return []

        # xywh → xyxy in pixel coords
        bx, by, bw, bh = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
        x1s = ((bx - bw / 2) / 640 * ow).astype(int)
        y1s = ((by - bh / 2) / 640 * oh).astype(int)
        x2s = ((bx + bw / 2) / 640 * ow).astype(int)
        y2s = ((by + bh / 2) / 640 * oh).astype(int)

        xyxy = np.stack([x1s, y1s, x2s, y2s], axis=1).astype(float)
        keep = nms(xyxy, conf_scores, iou_thresh)

        return [
            {"box": [int(x1s[i]), int(y1s[i]), int(x2s[i]), int(y2s[i])],
             "conf": float(conf_scores[i]), "cls": int(cls_ids[i])}
            for i in keep
        ]

    return []
