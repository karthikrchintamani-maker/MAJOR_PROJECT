# RoadEye Emergency Crash SOS Event Message
std_msgs/Header header

uint8 EVENT_MANUAL_SOS = 1
uint8 EVENT_CRASH_VERIFIED = 2

uint8 event_type
float64 latitude
float64 longitude
float32 impact_g_force
float32 pre_crash_speed_kmh
float32 post_crash_speed_kmh
string timestamp_utc
bool sms_sent
uint8 retry_count
string payload_text
