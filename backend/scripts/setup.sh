#!/bin/bash
# RoadEye System Setup Script for Ubuntu 24.04 LTS & ROS2 Humble

set -e

echo "=========================================================="
echo "      RoadEye Level-3 ADAS — Environment Setup"
echo "=========================================================="

sudo apt update
sudo apt install -y \
    build-essential \
    cmake \
    git \
    libyaml-cpp-dev \
    libopencv-dev \
    nlohmann-json3-dev \
    python3-pip \
    python3-colcon-common-extensions \
    ros-humble-desktop \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-tf2 \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs

# Install Node dependencies for Web Dashboard
if command -v npm &> /dev/null; then
    echo "Installing Dashboard NPM Dependencies..."
    cd dashboard && npm install && cd ..
fi

echo "Setup completed successfully!"
