#!/bin/bash
# In-container hotfix for Cartographer handoff issues (no full image rebuild).
# Paste sections into: docker exec -it roboracer_t7 bash
#
# Fixes:
#   1) Cartographer exit -6 (full_resolution_depth / 3D matcher Lua schema)
#   2) wall_follow /drive QoS vs ackermann_mux
#
# Requires: ros-humble-cartographer installed at /opt/ros/humble/...

set -e

echo "=== 1) Cartographer Lua (Humble-compatible) ==="
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
TRAJECTORY_BUILDER = TRAJECTORY_BUILDER_2D
EOF

test -f /race_ws/config/cartographer/roboracer_2d.lua || cat > /race_ws/config/cartographer/roboracer_2d.lua <<'EOF'
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

echo "=== 2) wall_follow /drive QoS -> RELIABLE (keep /scan BEST_EFFORT) ==="
WF="/race_ws/src/wall_follow_script/reactive_control/wall_follow_node.py"
if [ -f "$WF" ]; then
  python3 <<'PY'
from pathlib import Path
p = Path("/race_ws/src/wall_follow_script/reactive_control/wall_follow_node.py")
text = p.read_text()
old = """        drive_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )"""
new = """        drive_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )"""
if old in text:
    p.write_text(text.replace(old, new))
    print("patched drive_qos -> RELIABLE")
elif "drive_qos" in text and "RELIABLE" in text.split("drive_qos")[1][:400]:
    print("drive_qos already RELIABLE")
else:
    print("WARN: could not find drive_qos block — edit wall_follow_node.py manually")
PY
  grep -n "drive_qos" -A3 "$WF" | head -6
  cd /race_ws
  set +u
  source /opt/ros/humble/setup.bash
  source /race_ws/install/setup.bash 2>/dev/null || true
  set -u
  colcon build --packages-select reactive_control --symlink-install
  source /race_ws/install/setup.bash
else
  echo "WARN: $WF not found — skip colcon (image may use install-only copy)"
fi

echo "=== 3) Verify Cartographer config loads ==="
ros2 pkg prefix cartographer_ros
test -f /opt/ros/humble/share/cartographer/configuration_files/pose_graph.lua

echo "=== Done. Restart bringup in another terminal: ==="
echo "  ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true"
