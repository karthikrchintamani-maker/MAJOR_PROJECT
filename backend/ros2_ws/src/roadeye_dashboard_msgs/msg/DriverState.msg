# Driver Monitoring State Message
std_msgs/Header header

bool face_detected
float32 eye_closure_ratio   # PERCLOS metric (0.0: wide open, 1.0: fully closed)
float32 yawn_ratio          # Mouth opening ratio
float32 head_pitch_deg
float32 head_yaw_deg
float32 head_roll_deg

bool is_drowsy
bool is_distracted
float32 attentiveness_score # 0.0 (asleep/distracted) to 1.0 (fully attentive)
