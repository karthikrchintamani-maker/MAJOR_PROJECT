# RoadEye AI Models Directory

This directory contains tooling and documentation for training, exporting, and benchmarking AI perception models.

## Structure
- `scripts/export_onnx.py`: Converts trained PyTorch (`.pt`) weights into ONNX (`.onnx`) format for high-speed C++ deployment.
- `scripts/benchmark_onnx.py`: Benchmarks ONNX Runtime C++ execution performance (latency in ms and FPS).
- Model weights are located in `models/`:
  - `models/detection/`: YOLO11 Indian Road Detection
  - `models/segmentation/`: YOLO11 Road & Drivable Area Segmentation
  - `models/pothole/`: YOLOv8 Pothole Detection
  - `models/depth/`: UNet Depthwise Nano Monocular Depth

> [!NOTE]
> Per RoadEye architecture requirements, both `.pt` (training source) and `.onnx` (production deployment) formats are strictly maintained.
