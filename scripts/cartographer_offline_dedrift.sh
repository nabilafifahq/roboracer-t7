#!/usr/bin/env bash
# cartographer_offline_dedrift.sh — replay a rosbag through Cartographer OFFLINE
# with loop closure, export a de-drifted occupancy map (.pgm + .yaml + .pbstream).
#
# Usage (from repo root):
#   ./scripts/cartographer_offline_dedrift.sh <bag_dir> [out_dir]
#
# Example:
#   ./scripts/cartographer_offline_dedrift.sh testrun/june7_set7/lap3x testrun/june7_set7/maps
#
# Requires Docker and the cartographer-ekf image (or local ROS 2 + cartographer).
set -euo pipefail

BAG="${1:?Usage: $0 <bag_directory> [output_directory]}"
OUT="${2:-$(dirname "$BAG")/maps}"
IMAGE="${IMAGE:-nabilafifahq/roboracer-t7:cartographer-ekf}"
RESOLUTION="${MAP_RESOLUTION:-0.05}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$OUT"
BAG_ABS="$(cd "$(dirname "$BAG")" && pwd)/$(basename "$BAG")"
OUT_ABS="$(cd "$OUT" 2>/dev/null && pwd || (mkdir -p "$OUT" && cd "$OUT" && pwd))"

echo "=== Cartographer offline de-drift ==="
echo "  bag:  $BAG_ABS"
echo "  out:  $OUT_ABS"
echo "  image: $IMAGE"

docker run --rm \
  -v "$BAG_ABS:/data/bag:ro" \
  -v "$OUT_ABS:/data/out" \
  -v "$REPO_ROOT/config/cartographer:/config:ro" \
  "$IMAGE" \
  bash -lc '
    set -e
    source /opt/ros/humble/setup.bash
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

    echo "[1/2] cartographer_offline_node (loop closure ON) ..."
    cartographer_offline_node \
      -configuration_directory /config \
      -configuration_basename roboracer_2d_offline.lua \
      -bag_filenames /data/bag \
      -save_state_filename /data/out/dedrift.pbstream \
      2>&1 | tee /data/out/offline_log.txt

    echo "[2/2] pbstream -> occupancy grid ..."
    cartographer_pbstream_to_ros_map \
      -pbstream_filename /data/out/dedrift.pbstream \
      -map_filestem /data/out/track_dedrift \
      -resolution '"$RESOLUTION"' \
      2>&1 | tee /data/out/conv_log.txt

    ls -la /data/out/dedrift.pbstream /data/out/track_dedrift.pgm /data/out/track_dedrift.yaml
    echo "DONE — use track_dedrift.pgm/.yaml with build_raceline_from_bag.py"
  '

echo ""
echo "Next step:"
echo "  python3 scripts/build_raceline_from_bag.py \\"
echo "    --bag $BAG_ABS \\"
echo "    --pgm $OUT_ABS/track_dedrift.pgm \\"
echo "    --yaml $OUT_ABS/track_dedrift.yaml \\"
echo "    --outdir $(dirname "$OUT_ABS") --run-tum"
