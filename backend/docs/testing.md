# RoadEye — Testing & Simulation Guide

## Automated Unit Testing

RoadEye uses GoogleTest for C++ node & math utility testing.

Run all tests across the workspace:
```bash
cd ros2_ws
colcon test
colcon test-result --all
```

---

## Simulation Playback

### 1. RViz2 Visualization
```bash
ros2 launch launch/rviz.launch.py
```

### 2. CARLA Simulation Bridge
```bash
ros2 launch launch/carla_sim.launch.py
```
