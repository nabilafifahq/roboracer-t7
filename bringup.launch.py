#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description() -> LaunchDescription:
    livox_launch_dir = os.path.join(
        get_package_share_directory("livox_ros_driver2"), "launch_ROS2"
    )
    f1tenth_launch_dir = os.path.join(
        get_package_share_directory("f1tenth_stack"), "launch"
    )

    return LaunchDescription(
        [
            # Base drive stack: joy_node, joy_teleop, mux, ackermann_to_vesc, vesc_driver.
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(f1tenth_launch_dir, "no_lidar_bringup_launch.py")
                ),
                launch_arguments={
                    "joy_config": "/race_ws/config/joy_rc_steer_fix.yaml",
                }.items(),
            ),
            # Livox Mid-360 driver (publishes /livox/lidar)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(livox_launch_dir, "msg_MID360_launch.py")
                )
            ),
            # PointCloud2 -> LaserScan (Livox to /scan)
            Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="pointcloud_to_laserscan",
                output="screen",
                remappings=[
                    ("cloud_in", "/livox/lidar"),
                    ("scan", "/scan"),
                ],
                parameters=["/race_ws/config/pointcloud_to_laserscan_indoor.yaml"],
            ),
            # Wall-following autonomy node (reactive_control)
            Node(
                package="reactive_control",
                executable="wall_follow_node",
                name="wall_follow_node",
                output="screen",
                parameters=[
                    {
                        "target_speed_mps": 0.25,
                        "min_speed_mps": 0.0,
                        "max_speed_mps": 0.35,
                        "max_steering_angle_rad": 0.22,
                        "manual_override_latch": True,
                        "front_obstacle_distance_m": 1.0,
                        "side_obstacle_distance_m": 0.9,
                        "centering_gain": 0.8,
                        "steering_smoothing_alpha": 0.25,
                        "deadman_button_index": 1,
                        "lidar_drop_timeout_s": 2.0,
                    }
                ],
            ),
        ]
    )

