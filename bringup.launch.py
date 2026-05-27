#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import IncludeLaunchDescription, ExecuteProcess, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, EqualsSubstitution, PythonExpression
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory
import os


def _autonomy_one_of(autonomy: LaunchConfiguration, *modes: str) -> PythonExpression:
    """Python expression true when launch arg autonomy equals any of modes (Humble-safe; no OrCondition)."""
    if len(modes) == 1:
        return PythonExpression(["'", autonomy, "' == '", modes[0], "'"])
    parts = ["'", autonomy, "' == '", modes[0], "'"]
    for mode in modes[1:]:
        parts.extend([" or '", autonomy, "' == '", mode, "'"])
    return PythonExpression(parts)


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
        "/global_path",
        "/nav2_cmd_ackermann",
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

    # Derek / team raceline stack (see docs/AUTONOMY_MODES.md):
    #   raceline_path — TUM CSV -> /global_path only (what Derek/Ricky tested on car)
    #   raceline / nav2_vector_pursuit — CSV + Nav2 vector pursuit -> /nav2_cmd_ackermann
    derek_nav2_on = IfCondition(
        _autonomy_one_of(autonomy, "raceline", "nav2_vector_pursuit", "pure_pursuit")
    )
    derek_path_pub_on = IfCondition(
        _autonomy_one_of(
            autonomy,
            "raceline_path",
            "csv_path",
            "raceline",
            "nav2_vector_pursuit",
            "pure_pursuit",
        )
    )
    # Nabila geometric pursuit on /drive (experimental; not team-tested on UCSD-Blue).
    geometric_pursuit_on = IfCondition(
        _autonomy_one_of(autonomy, "raceline_pure_pursuit", "raceline_geometric")
    )
    wall_follow_on = UnlessCondition(
        _autonomy_one_of(
            autonomy,
            "raceline_path",
            "csv_path",
            "raceline",
            "nav2_vector_pursuit",
            "pure_pursuit",
            "raceline_pure_pursuit",
            "raceline_geometric",
        )
    )
    nav2_vector_launch = os.path.join(
        get_package_share_directory("roboracer_nav2_vector_pursuit"),
        "launch",
        "vector_pursuit_nav2_follow_global_path.launch.py",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "autonomy",
                default_value="wall_follow",
                description=(
                    "wall_follow (default); raceline_path or csv_path = Derek CSV->/global_path only (team-tested); "
                    "raceline or nav2_vector_pursuit = CSV + Nav2 vector pursuit; "
                    "raceline_pure_pursuit = geometric pursuit on /drive (experimental)."
                ),
            ),
            DeclareLaunchArgument(
                "raceline_csv",
                default_value="/race_ws/racelines/traj_race_cl.csv",
                description="TUM traj_race_cl.csv (or optimizer output) for Derek path publisher / Nav2 modes.",
            ),
            DeclareLaunchArgument(
                "pursuit_world_frame",
                default_value="odom",
                description="frame_id for /global_path and pursuit TF (odom with EKF; map with SLAM).",
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
            # Indoor autonomy: wall-follow (default), Derek raceline stack, or experimental geometric pursuit.
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
                        "max_steering_angle_rad": 0.70,
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
                condition=geometric_pursuit_on,
                parameters=[
                    {
                        "trajectory_csv": ParameterValue(LaunchConfiguration("raceline_csv"), value_type=str),
                        "lookahead_m": 0.55,
                        "wheelbase_m": 0.33,
                        "target_speed_mps": 0.12,
                        "max_steering_rad": 0.70,
                        "world_frame": ParameterValue(pursuit_world_frame, value_type=str),
                        "robot_frame": "base_link",
                    },
                ],
            ),
            # Derek: TUM CSV -> nav_msgs/Path on /global_path (team-tested CSV->topic conversion).
            Node(
                package="reactive_control",
                executable="traj_csv_path_publisher",
                name="traj_csv_path_publisher",
                output="screen",
                condition=derek_path_pub_on,
                parameters=[
                    {
                        "trajectory_csv": ParameterValue(LaunchConfiguration("raceline_csv"), value_type=str),
                        "path_topic": "/global_path",
                        "frame_id": ParameterValue(pursuit_world_frame, value_type=str),
                        "publish_hz": 1.0,
                        "step": 1,
                    },
                ],
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_vector_launch),
                condition=derek_nav2_on,
                launch_arguments={
                    "publish_map_odom_identity": "true",
                    "ackermann_topic": "/nav2_cmd_ackermann",
                }.items(),
            ),
        ]
    )
