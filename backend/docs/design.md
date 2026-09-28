# RoadEye — System Architecture & Modular Design

## Modular Layered Architecture

RoadEye is structured into 7 isolated execution layers:

```mermaid
graph TB
    subgraph Layer1["Layer 1 — Sensor Hub Firmware"]
        ESP1["ESP32 DevKit V1 (OBD, IMU, GPS, LiDAR)"]
        ESP2["ESP32-CAM (MJPEG Stream)"]
    end

    subgraph Layer2["Layer 2 — Sensor Bridge"]
        Bridge["roadeye_sensor_bridge (C++17)"]
    end

    subgraph Layer3["Layer 3 — Perception"]
        Vision["roadeye_perception (ONNX Runtime C++)"]
    end

    subgraph Layer4["Layer 4 — Sensor Fusion"]
        Fusion["roadeye_sensor_fusion (EKF)"]
    end

    subgraph Layer5["Layer 5 — Localization Interop"]
        Vehicle["roadeye_vehicle_interface (Autoware Msg Bridge)"]
    end

    subgraph Layer6["Layer 6 — Decision Engine"]
        Decision["roadeye_decision_node"]
        Emergency["roadeye_emergency (SIM800L Crash SOS)"]
    end

    subgraph Layer7["Layer 7 — Telemetry & Dashboard"]
        Dashboard["React + Vite + Leaflet Web Dashboard"]
    end

    Layer1 --> Layer2
    Layer2 --> Layer3
    Layer2 --> Layer4
    Layer3 --> Layer4
    Layer4 --> Layer5
    Layer4 --> Layer6
    Layer6 --> Layer7
```

## C++17 Principles
- **RAII & Smart Pointers**: `std::unique_ptr` and `std::shared_ptr` throughout.
- **Thread Safety**: Non-blocking UDP streams and mutex-guarded state locks.
- **Zero Raw Pointers**: Full adherence to modern C++ memory management standards.
