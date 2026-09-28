# Single Object Detection Message
uint32 id
string class_name
float32 confidence

# Bounding box in 2D image coordinates
float32 x_min
float32 y_min
float32 x_max
float32 y_max

# 3D spatial position relative to vehicle base_link
geometry_msgs/Point position
geometry_msgs/Vector3 velocity
float32 distance_m
float32 ttc_sec
