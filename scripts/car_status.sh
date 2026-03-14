#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-roboracer_t7}"
IMAGE="${IMAGE:-nabilafifahq/roboracer-t7:main-latest}"

echo "=== Docker status for RoboRacer ==="
echo "Container name target: ${CONTAINER_NAME}"
echo "Image target: ${IMAGE}"
echo

echo "--- Running containers matching name ---"
docker ps --filter "name=^/${CONTAINER_NAME}$"
echo

echo "--- Running containers from image ---"
docker ps --filter "ancestor=${IMAGE}"
