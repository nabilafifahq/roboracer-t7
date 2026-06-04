#!/bin/bash
# Terminal 2: run after launch_cartographer_mapping.sh is up.
set -e
source /race_ws/scripts/car_ros_env.sh

echo "=== nodes ==="
ros2 node list | grep -iE 'cartographer|ekf_filter|livox|pointcloud' || true

echo "=== /scan (8s) ==="
timeout 8 ros2 topic hz /scan --window 15 || true

echo "=== /odometry/filtered (8s) ==="
timeout 8 ros2 topic hz /odometry/filtered --window 15 || true

echo "=== /map (3s) ==="
timeout 3 ros2 topic hz /map --window 5 2>/dev/null || echo "(no /map — is use_cartographer bringup running?)"

echo "=== livox_frame TF ==="
timeout 2 ros2 run tf2_ros tf2_echo base_link livox_frame 2>/dev/null | head -n 8 || echo "(livox_frame missing — check bringup static_base_link_to_livox_frame)"

echo "=== odom -> base_link (3s) ==="
timeout 3 ros2 run tf2_ros tf2_echo odom base_link 2>/dev/null | head -n 8 || true

echo "=== map -> base_link (3s) — required before manual_map_logger world_frame:=map ==="
timeout 3 ros2 run tf2_ros tf2_echo map base_link 2>/dev/null | head -n 12 || echo "(FAIL: start launch_cartographer_mapping.sh and drive slowly)"

echo "=== done ==="
