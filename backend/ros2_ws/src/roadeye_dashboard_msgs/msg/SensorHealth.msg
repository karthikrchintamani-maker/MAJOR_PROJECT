# RoadEye Sensor Health Status
std_msgs/Header header

bool camera_ok
bool lidar_ok
bool gps_ok
bool imu_ok
bool obd_ok
bool gsm_ok

float32 camera_fps
float32 lidar_hz
float32 system_load_pct
float32 temperature_c
string status_message
