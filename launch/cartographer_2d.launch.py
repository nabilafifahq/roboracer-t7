#!/usr/bin/env python3
"""Launch Cartographer 2D SLAM for RoboRacer T7 (expects EKF odom + /scan)."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    use_sim_time = LaunchConfiguration("use_sim_time")
    configuration_directory = LaunchConfiguration("configuration_directory")
    configuration_basename = LaunchConfiguration("configuration_basename")
    resolution = LaunchConfiguration("resolution")

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument(
                "configuration_directory",
                default_value="/race_ws/config/cartographer",
            ),
            DeclareLaunchArgument("configuration_basename", default_value="roboracer_2d.lua"),
            DeclareLaunchArgument("resolution", default_value="0.05"),
            Node(
                package="cartographer_ros",
                executable="cartographer_node",
                name="cartographer_node",
                output="screen",
                parameters=[{"use_sim_time": use_sim_time}],
                arguments=[
                    "-configuration_directory",
                    configuration_directory,
                    "-configuration_basename",
                    configuration_basename,
                ],
                remappings=[
                    ("scan", "/scan"),
                    # Fused odometry matches EKF odom->base_link TF (not raw VESC /odom).
                    ("odom", "/odometry/filtered"),
                    ("imu", "/livox/imu"),
                ],
            ),
            Node(
                package="cartographer_ros",
                executable="cartographer_occupancy_grid_node",
                name="cartographer_occupancy_grid_node",
                output="screen",
                parameters=[
                    {"use_sim_time": use_sim_time, "resolution": resolution},
                ],
            ),
        ]
    )
