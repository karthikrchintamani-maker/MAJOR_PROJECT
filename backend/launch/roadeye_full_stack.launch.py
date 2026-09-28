import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    return LaunchDescription([
        # Sensor Bridge Node
        Node(
            package='roadeye_sensor_bridge',
            executable='sensor_bridge_node',
            name='roadeye_sensor_bridge',
            output='screen',
            parameters=[{'use_sim_fallback': True, 'udp_port': 8888}]
        ),

        # Perception Node
        Node(
            package='roadeye_perception',
            executable='perception_node',
            name='roadeye_perception',
            output='screen',
            parameters=[{
                'model_det_path': 'models/detection/yolo26n_indian_road_best.onnx',
                'model_seg_path': 'models/segmentation/yolo11m-road-seg.onnx',
                'model_pothole_path': 'models/pothole/pothole-detection-yolov8.onnx',
                'model_depth_path': 'models/depth/unet_depthwise_nano_best.onnx',
                'conf_threshold': 0.4,
                'use_sim_camera': True
            }]
        ),

        # Sensor Fusion Node
        Node(
            package='roadeye_sensor_fusion',
            executable='fusion_node',
            name='roadeye_sensor_fusion',
            output='screen',
            parameters=[{'weight_camera': 0.4, 'weight_lidar': 0.6}]
        ),

        # Decision Engine Node
        Node(
            package='roadeye_decision_node',
            executable='decision_node',
            name='roadeye_decision_node',
            output='screen',
            parameters=[{
                'fcw_ttc_threshold_sec': 2.5,
                'aeb_rec_ttc_threshold_sec': 1.2,
                'ldw_lane_offset_threshold_m': 0.55
            }]
        ),

        # Emergency Crash Handler Node
        Node(
            package='roadeye_emergency',
            executable='emergency_node',
            name='roadeye_emergency',
            output='screen',
            parameters=[{'crash_g_threshold': 4.0, 'emergency_phone_number': '+919876543210'}]
        ),

        # Vehicle Interface & Autoware Bridge
        Node(
            package='roadeye_vehicle_interface',
            executable='vehicle_interface_node',
            name='roadeye_vehicle_interface',
            output='screen'
        ),
    ])
