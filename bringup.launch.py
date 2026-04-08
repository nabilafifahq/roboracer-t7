#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription, ExecuteProcess, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description() -> LaunchDescription:
    livox_launch_dir = os.path.join(
        get_package_share_directory("livox_ros_driver2"), "launch_ROS2"
    )
    f1tenth_launch_dir = os.path.join(
        get_package_share_directory("f1tenth_stack"), "launch"
    )
    
    record_bag = LaunchConfiguration("record_bag")
    bag_dir = LaunchConfiguration("bag_dir")
    bag_name = LaunchConfiguration("bag_name")

    bag_topics = [
       "/drive",
       "/scan",
       "/tf",
       "/tf_static",
       "/odom",
       "/joy",
       '/diagnostics'
    ]

    bag_record = ExecuteProcess(
              condition=IfCondition(record_bag),
              cmd=[
                    "ros2", "bag", "record",
                    "-o", PathJoinSubstitution([bag_dir, bag_name]),

                    *bag_topics,
              ],
              output="screen",
    )


    return LaunchDescription(
        [   
            # (new) args:
            DeclareLaunchArgument("record_bag", default_value="false"),
            DeclareLaunchArgument("bag_dir", default_value="/race_ws/bags"),

            # (new) recorder:
            bag_record,

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
            # System monitor (publishes diagnostics)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        get_package_share_directory("ros2_system_monitor"),
                        "launch",
                        "system_monitor.launch.py",
                    )
                ),
                # Optional: disable monitors you don't want
                launch_arguments={
                    # "enable_cpu_monitor": "true",
                    # "enable_hdd_monitor": "true",
                    # "enable_mem_monitor": "true",
                    # "enable_net_monitor": "true",
                    # "enable_ntp_monitor": "false",
                }.items(),
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

