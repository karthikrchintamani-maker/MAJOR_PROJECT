# RoadEye — Dataflow & Processing Pipeline

## End-to-End Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    participant ESP as ESP32 Sensor Hub
    participant Bridge as roadeye_sensor_bridge
    participant Perception as roadeye_perception (ONNX)
    participant Fusion as roadeye_sensor_fusion
    participant Decision as roadeye_decision_node
    participant Emergency as roadeye_emergency
    participant Dash as Web Dashboard

    ESP->>Bridge: UDP Telemetry (Speed, RPM, GPS, IMU, LiDAR)
    Bridge->>Perception: Trigger Camera Frame Processing
    Perception->>Fusion: Publish Objects & Pothole Arrays
    Bridge->>Fusion: Publish Telemetry & LaserScan
    Fusion->>Decision: Fused Risk Score (0-100) & TTC
    Decision->>Dash: Publish WarningAlert.msg
    Decision->>Emergency: Verify Crash Criteria (IMU >4g + Speed drop)
    Emergency->>ESP: Dispatch SIM800L Emergency SMS
```

---

## EKF Fusion Equations

Spatial EKF state update combines Camera depth estimates \(d_{cam}\) and LiDAR ranges \(d_{lidar}\):

\[ d_{fused} = w_{cam} d_{cam} + w_{lidar} d_{lidar} \]

Where \(w_{cam} = 0.40\) and \(w_{lidar} = 0.60\).
