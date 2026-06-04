#!/bin/bash
# Log manual map CSV in map frame (Cartographer must be running).
set -e
source /race_ws/scripts/car_ros_env.sh
OUT="/race_ws/logs/map_cart_$(date +%Y%m%d_%H%M%S).csv"
mkdir -p /race_ws/logs
exec ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p robot_frame:=base_link \
  -p record_hz:=20.0 \
  -p output_csv:=${OUT}
