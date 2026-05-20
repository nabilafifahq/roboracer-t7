#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-roboracer_t7}"
IMAGE="${IMAGE:-nabilafifahq/roboracer-t7:main-latest}"
LAUNCH_FILE="${LAUNCH_FILE:-/race_ws/bringup.launch.py}"
# Optional extra args after the launch file, e.g.
# EXTRA_LAUNCH_ARGS='autonomy:=raceline_path raceline_csv:=/race_ws/racelines/traj_race_cl.csv'
# EXTRA_LAUNCH_ARGS='autonomy:=raceline raceline_csv:=/race_ws/racelines/traj_race_cl.csv pursuit_world_frame:=map use_slam:=true'
EXTRA_LAUNCH_ARGS="${EXTRA_LAUNCH_ARGS:-}"

CID="$(docker ps -q -f "name=^/${CONTAINER_NAME}$")"
if [[ -z "${CID}" ]]; then
  CID="$(docker ps -q -f "ancestor=${IMAGE}" | head -n 1)"
fi

if [[ -z "${CID}" ]]; then
  echo "No running container found."
  echo "Start one first with: ./scripts/car_run.sh"
  exit 1
fi

exec docker exec -it "${CID}" bash -lc \
  "source /opt/ros/humble/setup.bash && [ -f /race_ws/install/setup.bash ] && source /race_ws/install/setup.bash && ros2 launch ${LAUNCH_FILE} ${EXTRA_LAUNCH_ARGS}"
