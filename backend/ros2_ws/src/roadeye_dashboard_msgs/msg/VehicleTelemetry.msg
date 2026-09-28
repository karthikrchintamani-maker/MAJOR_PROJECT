# RoadEye Combined Vehicle Telemetry Message
std_msgs/Header header

float32 speed_kmh
float32 engine_rpm
float32 throttle_pos_pct
float32 brake_pressed
float32 coolant_temp_c
float32 battery_voltage

geometry_msgs/Vector3 linear_acceleration # IMU (m/s^2)
geometry_msgs/Vector3 angular_velocity   # IMU (rad/s)

float64 latitude
float64 longitude
float32 altitude
float32 gps_speed_kmh
float32 gps_heading_deg
uint8 gps_satellites
bool gps_valid
