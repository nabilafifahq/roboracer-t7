#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description() -> LaunchDescription:
    livox_launch_dir = os.path.join(
        get_package_share_directory("livox_ros_driver2"), "launch"
    )

    return LaunchDescription(
        [
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
                parameters=["docker/config/pointcloud_to_laserscan_indoor.yaml"],
            ),
            # Wall-following autonomy node (reactive_control)
            Node(
                package="reactive_control",
                executable="wall_follow_node",
                name="wall_follow_node",
                output="screen",
            ),
            # Ackermann command multiplexer
            Node(
                package="ackermann_mux",
                executable="ackermann_mux",
                name="ackermann_mux",
                output="screen",
                parameters=["config/ackermann_mux_topics.yaml"],
                remappings=[
                    # Ensure mux output goes to the topic expected by ackermann_to_vesc
                    ("ackermann_cmd", "drive"),
                ],
            ),
            # Ackermann to VESC bridge (ROS 1, typically run via bridge or separately)
            # If you are running this via a ROS 1 bridge, comment this out here and
            # launch it on the ROS 1 side instead.
            # Node(
            #     package="vesc_ackermann",
            #     executable="ackermann_to_vesc_node",
            #     name="ackermann_to_vesc_node",
            #     output="screen",
            # ),
        ]
    )

