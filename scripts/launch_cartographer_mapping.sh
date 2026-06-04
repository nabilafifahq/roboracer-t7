#!/bin/bash
# Terminal 1: full stack + EKF + Cartographer 2D (keep running).
set -e
source /race_ws/scripts/car_ros_env.sh
exec ros2 launch /race_ws/bringup.launch.py autonomy:=manual use_cartographer:=true
