#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-nabilafifahq/roboracer-t7:main-latest}"
CONTAINER_NAME="${CONTAINER_NAME:-roboracer_t7}"

echo "Using image: ${IMAGE}"
echo "Container name: ${CONTAINER_NAME}"

if docker ps -a --format '{{.Names}}' | grep -x "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "Removing existing container '${CONTAINER_NAME}'..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

echo "Starting container..."
exec docker run --rm -it \
  --name "${CONTAINER_NAME}" \
  --net=host \
  --ipc=host \
  --privileged \
  --device=/dev/input/js0 \
  --device=/dev/ttyACM0 \
  --device=/dev/ttyACM1 \
  -v /dev/sensors:/dev/sensors \
  -v /dev/bus/usb:/dev/bus/usb \
  "${IMAGE}"
