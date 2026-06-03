#!/usr/bin/env bash
# Save a Cartographer map two ways, from inside the running container:
#   1) <name>.pbstream  -> for Cartographer PURE LOCALIZATION (roboracer_2d_localization.lua)
#   2) <name>.pgm/.yaml -> for Nav2 / AMCL / RViz static layer
#
# Run while a Cartographer MAPPING session is live (use_cartographer:=true) and you
# have finished a good slow lap. Usage:
#   ./scripts/cartographer_save_map.sh [map_name] [out_dir]
# Defaults: map_name=track_$(date), out_dir=/race_ws/maps
set -euo pipefail

MAP_NAME="${1:-track_$(date +%Y%m%d_%H%M%S)}"
OUT_DIR="${2:-/race_ws/maps}"
mkdir -p "${OUT_DIR}"
PBSTREAM="${OUT_DIR}/${MAP_NAME}.pbstream"
PGM_BASE="${OUT_DIR}/${MAP_NAME}"

echo "=== 1/2  Cartographer state -> ${PBSTREAM} ==="
# finish_trajectory(0) closes the active trajectory, then write_state serializes it.
# no_paint_submaps=false keeps the occupancy data needed for localization.
ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory \
  "{trajectory_id: 0}" || echo "(finish_trajectory failed/already finished — continuing)"
ros2 service call /write_state cartographer_ros_msgs/srv/WriteState \
  "{filename: '${PBSTREAM}', include_unfinished_submaps: true}"

echo ""
echo "=== 2/2  Occupancy grid -> ${PGM_BASE}.pgm / .yaml ==="
# Requires the /map topic (cartographer_occupancy_grid_node is in the launch).
ros2 run nav2_map_server map_saver_cli -f "${PGM_BASE}" --ros-args -p save_map_timeout:=20.0

echo ""
echo "Saved:"
ls -la "${PBSTREAM}" "${PGM_BASE}.pgm" "${PGM_BASE}.yaml" 2>/dev/null || true
echo ""
echo "Race-day localization:"
echo "  ros2 launch /race_ws/launch/cartographer_2d.launch.py \\"
echo "    configuration_basename:=roboracer_2d_localization.lua \\"
echo "    load_state_filename:=${PBSTREAM}"
echo ""
echo "NOTE: finish_trajectory was called — this Cartographer session can no longer map."
echo "      Relaunch the stack to map again."
