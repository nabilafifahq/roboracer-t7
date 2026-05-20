#!/usr/bin/env python3
"""Nav2 bringup (vector pursuit controller) + bridge from /global_path + twist->Ackermann."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _opaque_setup(context, *args, **kwargs) -> list:
    pkg = get_package_share_directory("roboracer_nav2_vector_pursuit")
    nav2_dir = get_package_share_directory("nav2_bringup")

    default_map = os.path.join(pkg, "maps", "minimal.yaml")
    default_params = os.path.join(pkg, "config", "nav2_roboracer_vector_pursuit.yaml")
    bringup_launch = os.path.join(nav2_dir, "launch", "bringup_launch.py")

    map_yaml = LaunchConfiguration("map").perform(context) or default_map
    params_file = LaunchConfiguration("params_file").perform(context) or default_params
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context)
    slam = LaunchConfiguration("slam").perform(context)
    use_composition = LaunchConfiguration("use_composition").perform(context)

    path_topic = LaunchConfiguration("path_topic").perform(context)
    follow_path_action = LaunchConfiguration("follow_path_action").perform(context)
    cmd_vel_topic = LaunchConfiguration("cmd_vel_topic").perform(context)
    ackermann_topic = LaunchConfiguration("ackermann_topic").perform(context)

    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup_launch),
            launch_arguments={
                "map": map_yaml,
                "params_file": params_file,
                "use_sim_time": use_sim_time,
                "slam": slam,
                "use_composition": use_composition,
            }.items(),
        ),
        Node(
            package="roboracer_nav2_vector_pursuit",
            executable="global_path_follow_bridge",
            name="global_path_follow_bridge",
            parameters=[
                {
                    "path_topic": path_topic,
                    "follow_path_action": follow_path_action,
                }
            ],
            output="screen",
        ),
        Node(
            package="roboracer_nav2_vector_pursuit",
            executable="twist_to_ackermann",
            name="twist_to_ackermann",
            parameters=[
                {
                    "cmd_vel_topic": cmd_vel_topic,
                    "ackermann_topic": ackermann_topic,
                }
            ],
            output="screen",
        ),
    ]


def generate_launch_description() -> LaunchDescription:
    pkg = get_package_share_directory("roboracer_nav2_vector_pursuit")
    default_map = os.path.join(pkg, "maps", "minimal.yaml")
    default_params = os.path.join(pkg, "config", "nav2_roboracer_vector_pursuit.yaml")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "map",
                default_value=default_map,
                description="Occupancy grid yaml for map_server (small blank map by default).",
            ),
            DeclareLaunchArgument(
                "params_file",
                default_value=default_params,
                description="Nav2 params with vector_pursuit_controller FollowPath plugin.",
            ),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("slam", default_value="False"),
            DeclareLaunchArgument(
                "use_composition",
                default_value="False",
                description="Nav2 composition container (False = separate processes).",
            ),
            DeclareLaunchArgument(
                "publish_map_odom_identity",
                default_value="true",
                description="Publish static map->odom identity so odom-frame racelines align with Nav2 map frame.",
            ),
            DeclareLaunchArgument("path_topic", default_value="/global_path"),
            DeclareLaunchArgument("follow_path_action", default_value="/follow_path"),
            DeclareLaunchArgument("cmd_vel_topic", default_value="/cmd_vel"),
            DeclareLaunchArgument(
                "ackermann_topic",
                default_value="/nav2_cmd_ackermann",
                description="Connect to ackermann_mux (avoid publishing straight to /drive).",
            ),
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name="static_map_to_odom",
                arguments=["0", "0", "0", "0", "0", "0", "map", "odom"],
                condition=IfCondition(LaunchConfiguration("publish_map_odom_identity")),
            ),
            OpaqueFunction(function=_opaque_setup),
        ]
    )
