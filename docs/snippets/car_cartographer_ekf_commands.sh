# Copy-paste blocks for physical car (ucsd-blue / Pi).
# Run each section in order. Terminal 1 = bringup (keep running). Terminal 2 = preflight + logger.
#
# Image: derekh0803/roboracer-t7:cartographer-ekf-arm64

# --- On Pi host (SSH): pull + start container ---
# export DOCKER_USER=derekh0803
# export IMAGE=derekh0803/roboracer-t7:cartographer-ekf-arm64
# docker pull ${IMAGE}
# docker rm -f roboracer_t7 2>/dev/null || true
# docker run --rm -it --name roboracer_t7 --net=host --ipc=host --privileged \
#   --device=/dev/input/js0 --device=/dev/ttyACM0 --device=/dev/ttyACM1 \
#   -v /dev/sensors:/dev/sensors -v /dev/bus/usb:/dev/bus/usb \
#   ${IMAGE}

# --- Inside container: ROS env (run in EVERY new shell) ---
cat > /race_ws/scripts/car_ros_env.sh <<'EOF'
#!/bin/bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set +u
source /opt/ros/humble/setup.bash
if [ -f /race_ws/install/setup.bash ]; then
  source /race_ws/install/setup.bash
fi
set -u
EOF
chmod +x /race_ws/scripts/car_ros_env.sh

# --- Terminal 1: EKF + Cartographer + LiDAR + RC (leave running) ---
cat > /race_ws/scripts/launch_cartographer_mapping.sh <<'EOF'
#!/bin/bash
set -e
source /race_ws/scripts/car_ros_env.sh
exec ros2 launch /race_ws/bringup.launch.py autonomy:=wall_follow use_cartographer:=true
EOF
chmod +x /race_ws/scripts/launch_cartographer_mapping.sh

# Run Terminal 1:
#   /race_ws/scripts/launch_cartographer_mapping.sh

# --- Terminal 2: open second shell from Pi host ---
#   docker exec -it roboracer_t7 bash
#   source /race_ws/scripts/car_ros_env.sh

# --- Terminal 2: preflight (Step B) ---
cat > /race_ws/scripts/preflight_cartographer_map.sh <<'EOF'
#!/bin/bash
set -e
source /race_ws/scripts/car_ros_env.sh
echo "=== nodes (cartographer / ekf / lidar) ==="
ros2 node list | grep -E 'cartographer|ekf|livox|pointcloud' || true
echo "=== /scan (8s) ==="
timeout 8 ros2 topic hz /scan --window 15 || true
echo "=== /odometry/filtered (8s) ==="
timeout 8 ros2 topic hz /odometry/filtered --window 15 || true
echo "=== /map (3s) ==="
timeout 3 ros2 topic hz /map --window 5 2>/dev/null || echo "(no /map — is Terminal 1 bringup running?)"
echo "=== odom -> base_link (3s) ==="
timeout 3 ros2 run tf2_ros tf2_echo odom base_link 2>/dev/null | head -n 12 || true
echo "=== map -> base_link (3s) — must pass before logging ==="
timeout 3 ros2 run tf2_ros tf2_echo map base_link 2>/dev/null | head -n 12 || echo "(FAIL: start launch_cartographer_mapping.sh in another terminal)"
echo "=== done ==="
EOF
chmod +x /race_ws/scripts/preflight_cartographer_map.sh

# Run Terminal 2 preflight:
#   /race_ws/scripts/preflight_cartographer_map.sh
# Then watch TF until it updates (move car slowly 10–30s):
#   source /race_ws/scripts/car_ros_env.sh
#   ros2 run tf2_ros tf2_echo map base_link

# --- Terminal 2: manual map logger (Step C) ---
cat > /race_ws/scripts/run_manual_map_logger_map.sh <<'EOF'
#!/bin/bash
set -e
source /race_ws/scripts/car_ros_env.sh
OUT="/race_ws/logs/map_cart_$(date +%Y%m%d_%H%M%S).csv"
mkdir -p /race_ws/logs
exec ros2 run reactive_control manual_map_logger --ros-args \
  -p world_frame:=map \
  -p robot_frame:=base_link \
  -p record_hz:=20.0 \
  -p output_csv:=${OUT}
EOF
chmod +x /race_ws/scripts/run_manual_map_logger_map.sh

# Run logger (slow full lap, Ctrl+C when done):
#   /race_ws/scripts/run_manual_map_logger_map.sh

# --- Convert CSV -> TUM track input (Step E) ---
# Replace YYYYMMDD_HHMMSS with your file.
cat > /race_ws/scripts/convert_last_map_cart.sh <<'EOF'
#!/bin/bash
set -e
CSV="$(ls -t /race_ws/logs/map_cart_*.csv 2>/dev/null | head -n 1)"
if [ -z "$CSV" ]; then
  echo "No /race_ws/logs/map_cart_*.csv found" >&2
  exit 1
fi
mkdir -p /race_ws/raceline_data/inputs/tracks
OUT="/race_ws/raceline_data/inputs/tracks/from_manual_map.csv"
python3 /race_ws/scripts/manual_map_csv_to_tum_track.py \
  "$CSV" -o "$OUT" --drop-first 1
echo "Wrote $OUT from $CSV"
EOF
chmod +x /race_ws/scripts/convert_last_map_cart.sh

# --- Optional: raceline pursuit in map frame (Step G) ---
cat > /race_ws/scripts/launch_raceline_path_map.sh <<'EOF'
#!/bin/bash
set -e
source /race_ws/scripts/car_ros_env.sh
RACELINE="${1:-/race_ws/racelines/traj_race_cl.csv}"
exec ros2 launch /race_ws/bringup.launch.py \
  autonomy:=raceline_path \
  use_cartographer:=true \
  pursuit_world_frame:=map \
  raceline_csv:=${RACELINE}
EOF
chmod +x /race_ws/scripts/launch_raceline_path_map.sh
