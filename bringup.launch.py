#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription, ExecuteProcess, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, EqualsSubstitution
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.parameter_descriptions import ParameterValue
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
    autonomy = LaunchConfiguration("autonomy")
    pursuit_world_frame = LaunchConfiguration("pursuit_world_frame")
    use_slam = LaunchConfiguration("use_slam")

    # Post-race / analysis topics (extend as needed).
    bag_topics = [
        "/drive",
        "/ackermann_cmd",
        "/scan",
        "/livox/lidar",
        "/teleop",
        "/tf",
        "/tf_static",
        "/odom",
        "/odometry/filtered",
        "/livox/imu",
        "/joy",
        "/diagnostics",
        # VESC / drivetrain debug (motor not rolling, duty, current)
        "/commands/motor/speed",
        "/commands/servo/position",
        "/sensors/core",
    ]

    bag_record = ExecuteProcess(
        condition=IfCondition(record_bag),
        cmd=[
            "ros2",
            "bag",
            "record",
            "-o",
            PathJoinSubstitution([bag_dir, bag_name]),
            *bag_topics,
        ],
        output="screen",
    )

    wall_follow_on = UnlessCondition(
        EqualsSubstitution(autonomy, "raceline_pure_pursuit"),
    )
    pursuit_on = IfCondition(
        EqualsSubstitution(autonomy, "raceline_pure_pursuit"),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "autonomy",
                default_value="wall_follow",
                description="'wall_follow' (default) or 'raceline_pure_pursuit' (TUM CSV + geometric pure pursuit on /drive).",
            ),
            DeclareLaunchArgument(
                "raceline_csv",
                default_value="/race_ws/racelines/traj_race_cl.csv",
                description="Trajectory file for raceline_pure_pursuit (TUM traj_race_cl.csv columns).",
            ),
            DeclareLaunchArgument(
                "pursuit_world_frame",
                default_value="odom",
                description="TF frame for raceline_pure_pursuit (odom with EKF; map with SLAM).",
            ),
            DeclareLaunchArgument(
                "use_slam",
                default_value="false",
                description="If true, launch slam_toolbox async mapping (publishes map->odom). Log manual_map with world_frame:=map; use pursuit_world_frame:=map when driving that raceline.",
            ),
            DeclareLaunchArgument("record_bag", default_value="false"),
            DeclareLaunchArgument("bag_dir", default_value="/race_ws/bags"),
            DeclareLaunchArgument("bag_name", default_value="race_bag"),
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
            # Livox Mid-360: Docker build patches msg_MID360_launch.py to use frame_id "laser"
            # so PointCloud2 matches f1tenth static TF base_link -> laser (see docs/07_TROUBLESHOOTING §10).
            # Livox Mid-360 driver (publishes /livox/lidar)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(livox_launch_dir, "msg_MID360_launch.py")
                )
            ),
            # System monitor (publishes /diagnostics for rosbag + post-race analysis)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        get_package_share_directory("ros2_system_monitor"),
                        "launch",
                        "system_monitor.launch.py",
                    )
                ),
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
            # Fuse wheel odometry + Livox IMU into smooth odom->base_link (vesc_to_odom publish_tf is false).
            Node(
                package="robot_localization",
                executable="ekf_node",
                name="ekf_filter_node",
                output="screen",
                parameters=["/race_ws/config/ekf_car.yaml"],
            ),
            # Optional SLAM: map->odom (EKF keeps odom->base_link). For competition raceline CSV in map frame.
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(
                        get_package_share_directory("slam_toolbox"),
                        "launch",
                        "online_async_launch.py",
                    )
                ),
                launch_arguments={
                    "slam_params_file": "/race_ws/config/slam_toolbox_mapper_online_async.yaml",
                }.items(),
                condition=IfCondition(EqualsSubstitution(use_slam, "true")),
            ),
            # Indoor autonomy: reactive wall-follow (default) OR TUM raceline + geometric pure pursuit.
            Node(
                package="reactive_control",
                executable="wall_follow_node",
                name="wall_follow_node",
                output="screen",
                condition=wall_follow_on,
                parameters=[
                    {
                        "target_speed_mps": 0.1,
                        "min_speed_mps": 0.0,
                        "max_speed_mps": 0.12,
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
            Node(
                package="reactive_control",
                executable="raceline_pure_pursuit_node",
                name="raceline_pure_pursuit",
                output="screen",
                condition=pursuit_on,
                parameters=[
                    {
                        "trajectory_csv": ParameterValue(LaunchConfiguration("raceline_csv"), value_type=str),
                        "lookahead_m": 0.55,
                        "wheelbase_m": 0.33,
                        "target_speed_mps": 0.12,
                        "max_steering_rad": 0.28,
                        "world_frame": ParameterValue(pursuit_world_frame, value_type=str),
                        "robot_frame": "base_link",
                    },
                ],
            ),
        ]
    )
