"""
RoadEye Backend Configuration
Central config loaded from YAML files and environment variables.
"""
import os
import yaml
from pathlib import Path

# ─── Root Paths ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent
ROOT = BACKEND_DIR.parent  # project root
MODELS_DIR = BACKEND_DIR / "models" if (BACKEND_DIR / "models").exists() else ROOT / "models"
CONFIGS_DIR = MODELS_DIR / "configs"

# ─── Server Config ────────────────────────────────────────────────────────────
HOST = os.environ.get("ROADEYE_HOST", "0.0.0.0")
PORT = int(os.environ.get("ROADEYE_PORT", 5001))
DEBUG = os.environ.get("ROADEYE_DEBUG", "false").lower() == "true"

# ─── CORS / Frontend ──────────────────────────────────────────────────────────
ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:4173", "http://127.0.0.1:5173"]

# ─── Model Paths ─────────────────────────────────────────────────────────────
MODEL_PATHS = {
    "detection":    MODELS_DIR / "detection"  / "yolo26n_indian_road_best.onnx",
    "segmentation": MODELS_DIR / "segmentation" / "yolo11m-road-seg.onnx",
    "pothole":      MODELS_DIR / "pothole"    / "pothole-detection-yolov8.onnx",
    "depth":        MODELS_DIR / "depth"      / "unet_depthwise_nano_best.onnx",
}

PT_MODEL_PATHS = {
    "detection":    MODELS_DIR / "detection"  / "yolo26n_indian_road_best.pt",
    "segmentation": MODELS_DIR / "segmentation" / "yolo11m-road-seg.pt",
    "pothole":      MODELS_DIR / "pothole"    / "pothole-detection-yolov8.pt",
    "depth":        MODELS_DIR / "depth"      / "unet_depthwise_nano_best.pt",
}

# ─── Inference Thresholds ─────────────────────────────────────────────────────
CONF_THRESH = float(os.environ.get("ROADEYE_CONF", 0.40))
NMS_THRESH  = float(os.environ.get("ROADEYE_NMS",  0.45))
INPUT_SIZE  = (640, 640)          # NCHW model input

# ─── Camera ───────────────────────────────────────────────────────────────────
WEBCAM_INDEX = int(os.environ.get("ROADEYE_WEBCAM", 0))
ESPCAM_URL   = os.environ.get("ROADEYE_ESPCAM", "http://192.168.4.2/stream")
UPLOAD_FOLDER = BACKEND_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# ─── Classes ─────────────────────────────────────────────────────────────────
def _load_yaml(path: Path) -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

_cls_cfg = _load_yaml(CONFIGS_DIR / "classes.yaml")

DETECTION_CLASSES: dict[int, str] = {
    k: v for k, v in (_cls_cfg.get("detection", {}).get("names", {}) or {}).items()
}
POTHOLE_CLASSES: dict[int, str] = {
    k: v for k, v in (_cls_cfg.get("pothole", {}).get("names", {}) or {}).items()
}

# Default fallbacks if yaml missing
if not DETECTION_CLASSES:
    DETECTION_CLASSES = {
        0: "Ambulance", 1: "Autorickshaw", 2: "Barricade", 3: "Bike",
        7: "Bus", 11: "Car", 27: "MotorBike", 29: "Person",
        39: "Traffic Signal", 41: "Truck",
    }

if not POTHOLE_CLASSES:
    POTHOLE_CLASSES = {
        0: "Longitudinal Crack", 1: "Transverse Crack",
        2: "Alligator Crack", 3: "Pothole", 4: "Other"
    }

# ─── GIT LFS stub detection ───────────────────────────────────────────────────
LFS_MAGIC = b"version https://git-lfs.github.com/spec"

def is_lfs_stub(path: Path) -> bool:
    """Return True if a model file is a Git LFS pointer (not real weights)."""
    try:
        if path.stat().st_size > 4096:   # real models are MBs
            return False
        with open(path, "rb") as f:
            header = f.read(50)
        return header.startswith(LFS_MAGIC)
    except Exception:
        return True  # treat missing/unreadable as stub
