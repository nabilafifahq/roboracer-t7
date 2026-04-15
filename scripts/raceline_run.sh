#!/usr/bin/env bash
set -euo pipefail

# Simple runner for the TUM global raceline optimizer container.
#
# Usage examples:
#   ./scripts/raceline_run.sh
#   IMAGE=roboracer-t7-raceline:latest ./scripts/raceline_run.sh
#
# Inside the container, run (example):
#   python main_globaltraj.py
#
# To persist your edits/outputs, mount a local folder:
#   DATA_DIR="$PWD/raceline_data" ./scripts/raceline_run.sh

IMAGE="${IMAGE:-roboracer-t7-raceline:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-roboracer_raceline}"
DATA_DIR="${DATA_DIR:-}"

echo "Using image: ${IMAGE}"
echo "Container name: ${CONTAINER_NAME}"

if docker ps -a --format '{{.Names}}' | grep -x "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "Removing existing container '${CONTAINER_NAME}'..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

DOCKER_ARGS=(
  --rm -it
  --name "${CONTAINER_NAME}"
  -w /work/global_racetrajectory_optimization
)

# Optional: mount a host folder to persist inputs/params/outputs.
# Expected layout under DATA_DIR:
#   inputs/   params/   outputs/
if [[ -n "${DATA_DIR}" ]]; then
  if [[ ! -d "${DATA_DIR}" ]]; then
    echo "ERROR: DATA_DIR does not exist: ${DATA_DIR}" >&2
    exit 1
  fi
  echo "Mounting DATA_DIR: ${DATA_DIR}"
  DOCKER_ARGS+=(
    -v "${DATA_DIR}:/data"
  )
  echo "Inside container:"
  echo "  - copy /data/inputs/* into ./inputs/   (or mount your own repo fork)"
  echo "  - copy /data/params/* into ./params/"
  echo "  - run: python main_globaltraj.py"
  echo "  - copy ./outputs/* to /data/outputs/ to persist on host"
fi

exec docker run "${DOCKER_ARGS[@]}" "${IMAGE}"

