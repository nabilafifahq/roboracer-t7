#!/usr/bin/env python3
"""Launch Cartographer 2D SLAM for RoboRacer T7 (expects EKF odom + /scan).

Mapping (default):
    ros2 launch /race_ws/launch/cartographer_2d.launch.py

Pure localization on a saved map (race day):
    ros2 launch /race_ws/launch/cartographer_2d.launch.py \
      configuration_basename:=roboracer_2d_localization.lua \
      load_state_filename:=/race_ws/maps/<track>.pbstream
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    use_sim_time = LaunchConfiguration("use_sim_time")
    configuration_directory = LaunchConfiguration("configuration_directory")
    configuration_basename = LaunchConfiguration("configuration_basename")
    resolution = LaunchConfiguration("resolution")
    load_state_filename = LaunchConfiguration("load_state_filename")

    # Cartographer node argument lists differ only by the optional saved-map flag.
    # Using two Nodes (mutually exclusive conditions) keeps the -load_state_filename
    # flag out of the argv entirely when no map is provided.
    common_args = [
        "-configuration_directory",
        configuration_directory,
        "-configuration_basename",
        configuration_basename,
    ]
    has_state = PythonExpression(["'", load_state_filename, "' != ''"])

    cartographer_mapping = Node(
        package="cartographer_ros",
        executable="cartographer_node",
        name="cartographer_node",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        arguments=common_args,
        remappings=[
            ("scan", "/scan"),
            # Fused odometry matches EKF odom->base_link TF (not raw VESC /odom).
            ("odom", "/odometry/filtered"),
            ("imu", "/livox/imu"),
        ],
        condition=UnlessCondition(has_state),
    )

    cartographer_localization = Node(
        package="cartographer_ros",
        executable="cartographer_node",
        name="cartographer_node",
        output="screen",
        parameters=[{"use_sim_time": use_sim_time}],
        # -load_state_filename freezes the saved map; pair with the *_localization.lua basename.
        arguments=common_args + ["-load_state_filename", load_state_filename],
        remappings=[
            ("scan", "/scan"),
            ("odom", "/odometry/filtered"),
            ("imu", "/livox/imu"),
        ],
        condition=IfCondition(has_state),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument(
                "configuration_directory",
                default_value="/race_ws/config/cartographer",
            ),
            DeclareLaunchArgument(
                "configuration_basename",
                default_value="roboracer_2d.lua",
                description="roboracer_2d.lua (mapping) or roboracer_2d_localization.lua (saved map).",
            ),
            DeclareLaunchArgument("resolution", default_value="0.05"),
            DeclareLaunchArgument(
                "load_state_filename",
                default_value="",
                description="Path to a saved .pbstream for pure localization. Empty = live mapping.",
            ),
            cartographer_mapping,
            cartographer_localization,
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
