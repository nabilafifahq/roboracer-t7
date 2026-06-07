#!/usr/bin/env bash
set -euo pipefail

source /opt/ros/humble/setup.bash
source /race_ws/install/setup.bash
source /opt/orbslam3_ws/install/setup.bash

echo "=== Core camera/imu topics ==="
ros2 topic list | grep -E '^/oak/rgb/image_raw$|^/oak/imu/data$|^/camera/image_raw$|^/imu$|^/livox/imu$|^/scan$' || true
echo ""
echo "=== Rates ==="
timeout 8s ros2 topic hz /oak/rgb/image_raw || true
timeout 8s ros2 topic hz /oak/imu/data || true
