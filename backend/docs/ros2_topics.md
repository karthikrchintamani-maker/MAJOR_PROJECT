# RoadEye — ROS2 Topic Directory

| Topic Name | Message Type | Rate (Hz) | Publisher Node | Description |
|---|---|---|---|---|
| `/roadeye/vehicle/telemetry` | `roadeye_dashboard_msgs/VehicleTelemetry` | 20 Hz | `sensor_bridge_node` | Combined speed, RPM, GPS & IMU telemetry |
| `/roadeye/sensor/gps` | `sensor_msgs/NavSatFix` | 5 Hz | `sensor_bridge_node` | Raw GPS fix data |
| `/roadeye/sensor/imu` | `sensor_msgs/Imu` | 50 Hz | `sensor_bridge_node` | Raw 6-DOF IMU data |
| `/roadeye/sensor/lidar` | `sensor_msgs/LaserScan` | 20 Hz | `sensor_bridge_node` | LaserScan distance data |
| `/roadeye/perception/objects` | `roadeye_dashboard_msgs/ObjectDetectionArray` | 15 Hz | `perception_node` | 2D/3D Object detections |
| `/roadeye/perception/potholes` | `roadeye_dashboard_msgs/PotholeArray` | 15 Hz | `perception_node` | Detected pothole polygons & depth |
| `/roadeye/perception/lane_state` | `roadeye_dashboard_msgs/LaneState` | 15 Hz | `perception_node` | Lane boundary deviation & center offset |
| `/roadeye/fusion/risk_score` | `std_msgs/Float32` | 20 Hz | `fusion_node` | Spatial Risk Score (0-100) |
| `/roadeye/warnings` | `roadeye_dashboard_msgs/WarningAlert` | 20 Hz | `decision_node` | ADAS warning alerts (FCW, LDW, AEB rec) |
| `/roadeye/emergency/event` | `roadeye_dashboard_msgs/EmergencyEvent` | Event | `emergency_node` | Verified crash SOS events |
