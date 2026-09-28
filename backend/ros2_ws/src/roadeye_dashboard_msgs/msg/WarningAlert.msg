# RoadEye ADAS Warning Alert Message
std_msgs/Header header

uint8 ALERT_NONE = 0
uint8 FCW = 1
uint8 AEB_RECOMMENDATION = 2
uint8 LDW_LEFT = 3
uint8 LDW_RIGHT = 4
uint8 LKA_RECOMMENDATION = 5
uint8 POTHOLE_AHEAD = 6
uint8 DROWSINESS_WARNING = 7
uint8 SPEEDING_WARNING = 8

uint8 alert_type
uint8 severity        # 1: LOW, 2: MEDIUM, 3: HIGH, 4: CRITICAL
string message
float32 time_to_collision # Seconds (TTC)
float32 distance_to_target # Meters
float32 current_speed      # km/h
bool audio_trigger
bool haptic_trigger
