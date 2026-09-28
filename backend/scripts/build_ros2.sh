#!/bin/bash
# RoadEye ROS2 Workspace Build Script

set -e

echo "Building RoadEye ROS2 C++17 Workspace..."

cd ros2_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
cd ..

echo "Workspace build complete!"
