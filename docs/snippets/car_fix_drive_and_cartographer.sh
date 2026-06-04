#!/bin/bash
# Hotfix on car: Cartographer trajectory_builder_2d crash + restore RC manual drive.
# Paste: docker exec -it roboracer_t7 bash -c 'bash /tmp/fix.sh'
# Or copy this file to /tmp/fix.sh inside container.

set -e
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set +u
source /opt/ros/humble/setup.bash
[ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash
set -u

echo "=== FIX Cartographer trajectory_builder.lua ==="
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

echo "=== VESC device (UCSD-Blue: ttyACM0) ==="
mkdir -p /dev/sensors
ln -sf /dev/ttyACM0 /dev/sensors/vesc
ls -l /dev/sensors/vesc

echo "=== DONE ==="
echo "Ctrl+C old launch, then run:"
echo "  ros2 launch /race_ws/bringup.launch.py autonomy:=manual use_cartographer:=true"
echo "RC: deadman ON, /teleop wins over /drive (no wall_follow in manual mode)"
