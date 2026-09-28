# RoadEye — Deployment Guide (RPi 5 & Jetson Orin)

## Raspberry Pi 5 System Setup

1. Flash **Ubuntu 24.04 LTS (64-bit)** to NVMe SSD or high-speed microSD.
2. Install ROS2 Humble Desktop:
   ```bash
   sudo apt update && sudo apt install -y ros-humble-desktop
   ```
3. Clone and build RoadEye workspace:
   ```bash
   git clone https://github.com/MOHAMMADARFATHWR/roadeye_models.git RoadEye
   cd RoadEye
   ./scripts/setup.sh
   ./scripts/build_ros2.sh
   ```

---

## Jetson Orin Nano Acceleration (Optional)

To enable TensorRT acceleration for ONNX models:
```bash
trtexec --onnx=models/detection/yolo26n_indian_road_best.onnx --saveEngine=models/detection/yolo26n_indian_road_best.engine --fp16
```
