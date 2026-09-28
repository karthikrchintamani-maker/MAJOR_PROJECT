import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # CARLA Simulator Bridge Node
        Node(
            package='roadeye_sensor_bridge',
            executable='sensor_bridge_node',
            name='carla_roadeye_bridge',
            output='screen',
            parameters=[{'use_sim_fallback': True}]
        ),
        # Full Stack Launcher Integration
        Node(
            package='roadeye_decision_node',
            executable='decision_node',
            name='carla_decision_evaluator',
            output='screen'
        )
    ])
