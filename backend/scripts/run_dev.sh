#!/bin/bash
# RoadEye Local Development & Launch Script

set -e

echo "Starting RoadEye ADAS Stack & Dashboard..."

# Launch Dashboard in background if node available
if command -v npm &> /dev/null; then
    (cd dashboard && npm run dev) &
fi

# Launch ROS2 Stack
ros2 launch launch/roadeye_full_stack.launch.py
