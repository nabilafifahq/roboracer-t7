#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-nabilafifahq/roboracer-t7:main-latest}"
CONTAINER_NAME="${CONTAINER_NAME:-roboracer_t7}"
LIVOX_MID360_CONFIG_PATH="${LIVOX_MID360_CONFIG_PATH:-}"

echo "Using image: ${IMAGE}"
echo "Container name: ${CONTAINER_NAME}"
if [[ -n "${LIVOX_MID360_CONFIG_PATH}" ]]; then
  if [[ ! -f "${LIVOX_MID360_CONFIG_PATH}" ]]; then
    echo "ERROR: LIVOX_MID360_CONFIG_PATH does not exist: ${LIVOX_MID360_CONFIG_PATH}" >&2
    exit 1
  fi
  echo "Using custom MID360 config: ${LIVOX_MID360_CONFIG_PATH}"
fi

if docker ps -a --format '{{.Names}}' | grep -x "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "Removing existing container '${CONTAINER_NAME}'..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

DOCKER_ARGS=(
  --rm -it
  --name "${CONTAINER_NAME}"
  --net=host
  --ipc=host
  --privileged
  --device=/dev/input/js0
  --device=/dev/ttyACM0
  --device=/dev/ttyACM1
  -v /dev/sensors:/dev/sensors
  -v /dev/bus/usb:/dev/bus/usb
)

if [[ -n "${LIVOX_MID360_CONFIG_PATH}" ]]; then
  DOCKER_ARGS+=(
    -v "${LIVOX_MID360_CONFIG_PATH}:/race_ws/src/drivers/livox_ros_driver2/config/MID360_config.json:ro"
  )
fi

echo "Starting container..."
exec docker run "${DOCKER_ARGS[@]}" "${IMAGE}"
