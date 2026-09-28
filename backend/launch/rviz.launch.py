import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    rviz_config_path = os.path.join(os.getcwd(), 'simulation', 'roadeye_default.rviz')
    return LaunchDescription([
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config_path],
            output='screen'
        )
    ])
