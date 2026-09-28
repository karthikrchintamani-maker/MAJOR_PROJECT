# RoadEye — Troubleshooting & Debugging Manual

## Common Issues & Solutions

### 1. ESP32 UDP Telemetry Not Received
**Symptom**: `/roadeye/vehicle/telemetry` topic is silent.
**Fix**:
- Ensure RPi 5 and ESP32 DevKit V1 are connected to the same WiFi network (`RoadEye_AP`).
- Verify port 8888 is open:
  ```bash
  netstat -an | grep 8888
  ```

### 2. ONNX Model Load Failure
**Symptom**: `perception_node` exits with model file error.
**Fix**:
- Check that `.onnx` model files exist in `models/`:
  ```bash
  ls -lh models/detection/yolo26n_indian_road_best.onnx
  ```

### 3. SIM800L AT Command Timeout
**Symptom**: Emergency SOS fails to dispatch SMS.
**Fix**:
- Verify SIM800L module has adequate power supply (requires 3.7V - 4.2V with 2A peak current capability).
