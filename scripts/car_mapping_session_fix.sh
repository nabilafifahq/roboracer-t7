#!/bin/bash
# Run INSIDE container (docker exec -it roboracer_t7 bash).
# Fixes configs corrupted by bad terminal paste + Cartographer Lua + prep for mapping.
set -euo pipefail

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set +u
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
set -u

echo "========== 1) Cartographer Lua (Humble nested TRAJECTORY_BUILDER) =========="
mkdir -p /race_ws/config/cartographer

cat > /race_ws/config/cartographer/map_builder.lua <<'EOF'
dofile('/opt/ros/humble/share/cartographer/configuration_files/map_builder.lua')
MAP_BUILDER.use_trajectory_builder_2d = true
MAP_BUILDER.use_trajectory_builder_3d = false
MAP_BUILDER.num_background_threads = 2
EOF

cat > /race_ws/config/cartographer/trajectory_builder.lua <<'EOF'
dofile('/opt/ros/humble/share/cartographer/configuration_files/trajectory_builder.lua')
TRAJECTORY_BUILDER_2D.min_range = 0.20
TRAJECTORY_BUILDER_2D.max_range = 12.0
TRAJECTORY_BUILDER_2D.min_z = -0.15
TRAJECTORY_BUILDER_2D.max_z = 0.35
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 5.0
TRAJECTORY_BUILDER_2D.num_accumulated_range_data = 1
TRAJECTORY_BUILDER_2D.use_imu_data = false
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true
TRAJECTORY_BUILDER_2D.motion_filter.max_time_seconds = 5.0
TRAJECTORY_BUILDER_2D.motion_filter.max_distance_meters = 0.05
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = 0.12
EOF

cat > /race_ws/config/cartographer/roboracer_2d.lua <<'EOF'
include "map_builder.lua"
include "trajectory_builder.lua"
options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,
  map_frame = "map",
  tracking_frame = "base_link",
  published_frame = "base_link",
  odom_frame = "odom",
  provide_odom_frame = false,
  publish_frame_projected_to_2d = true,
  use_odometry = true,
  use_nav_sat = false,
  use_landmarks = false,
  num_laser_scans = 1,
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,
  num_point_clouds = 0,
  lookup_transform_timeout_sec = 0.3,
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,
  trajectory_publish_period_sec = 30e-3,
  rangefinder_sampling_ratio = 1.0,
  odometry_sampling_ratio = 1.0,
  fixed_frame_pose_sampling_ratio = 1.0,
  imu_sampling_ratio = 1.0,
  landmarks_sampling_ratio = 1.0,
}
MAP_BUILDER.use_trajectory_builder_2d = true
return options
EOF

echo "========== 2) Restore pointcloud + joy configs (clean YAML) =========="
cat > /race_ws/config/pointcloud_to_laserscan_indoor.yaml <<'EOF'
pointcloud_to_laserscan:
  ros__parameters:
    target_frame: laser
    transform_tolerance: 0.2
    min_height: -0.15
    max_height: 0.35
    angle_min: -1.5708
    angle_max: 1.5708
    angle_increment: 0.00872665
    scan_time: 0.1
    range_min: 0.20
    range_max: 12.0
    use_inf: true
    qos_overrides:
      /livox/lidar.subscription:
        reliability: reliable
        history: keep_last
        depth: 256
EOF

cat > /race_ws/config/joy_rc_steer_fix.yaml <<'EOF'
joy:
  ros__parameters:
    dev: /dev/input/js0
    deadzone: 0.04
    autorepeat_rate: 40.0

joy_teleop:
  ros__parameters:
    human_control:
      type: topic
      interface_type: ackermann_msgs/msg/AckermannDriveStamped
      topic_name: /teleop
      deadman_buttons: [1]
      axis_mappings:
        drive-speed:
          axis: 1
          scale: -0.50
          offset: 0.0
        drive-steering_angle:
          axis: 3
          scale: 0.85
          offset: 0.0
EOF

echo "========== 3) VESC device =========="
mkdir -p /dev/sensors
ln -sf /dev/ttyACM0 /dev/sensors/vesc
ls -l /dev/sensors/vesc

echo "========== DONE =========="
echo ""
echo "NEXT — use TWO terminals:"
echo "  Terminal 1 (keep running):"
echo "    ros2 launch /race_ws/bringup.launch.py autonomy:=manual use_cartographer:=true"
echo "  Wait until: ros2 run tf2_ros tf2_echo map base_link  (updates when you move car)"
echo "  Terminal 2:"
echo "    /race_ws/scripts/run_manual_map_logger_map.sh"
echo ""
echo "Do NOT run manual_map_logger without Terminal 1 bringup running."
