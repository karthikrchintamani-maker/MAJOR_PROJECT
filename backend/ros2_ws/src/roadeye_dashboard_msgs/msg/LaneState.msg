# Lane Tracking State Message
std_msgs/Header header

bool left_lane_detected
bool right_lane_detected

float32 left_lane_distance  # Meters from vehicle centerline to left lane
float32 right_lane_distance # Meters from vehicle centerline to right lane
float32 center_offset       # Meters offset from lane center (+: right, -: left)
float32 lane_width          # Meters
float32 heading_error_deg   # Vehicle angle relative to lane direction

bool lane_departure_left
bool lane_departure_right
