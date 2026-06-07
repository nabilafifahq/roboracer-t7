#!/usr/bin/env bash
set -euo pipefail

source /opt/ros/humble/setup.bash
source /opt/orbslam3_ws/install/setup.bash

echo "=== ros2_orb_slam3 executables ==="
ros2 pkg executables ros2_orb_slam3
