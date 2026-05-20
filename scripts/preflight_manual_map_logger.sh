#!/bin/bash
# Quick checks before manual_map_logger hallway capture (see docker/dockerfile + docs).
# Run inside the race container after bringup, same RMW as the stack.
set -euo pipefail
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"
source /opt/ros/humble/setup.bash
if [ -f /race_ws/install/setup.bash ]; then
  source /race_ws/install/setup.bash
fi

echo "=== RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION ==="
echo "=== vesc.yaml publish_tf (installed) ==="
vesc="$(find /race_ws/install -path '*/share/*/config/vesc.yaml' -print -quit 2>/dev/null || true)"
if [ -z "$vesc" ]; then
  echo "WARN: could not find installed vesc.yaml under /race_ws/install"
else
  grep -n "publish_tf" "$vesc" || true
fi

echo "=== /odom (8s sample) ==="
timeout 8 ros2 topic hz /odom --window 15 || true

echo "=== /odometry/filtered (8s sample) ==="
timeout 8 ros2 topic hz /odometry/filtered --window 15 || true

echo "=== /livox/lidar (8s sample) ==="
timeout 8 ros2 topic hz /livox/lidar --window 10 || true

echo "=== /scan (8s sample) ==="
timeout 8 ros2 topic hz /scan --window 15 || true

echo "=== /tf publishers (summary) ==="
ros2 topic info /tf -v 2>/dev/null | head -n 40 || true

echo "=== done ==="
