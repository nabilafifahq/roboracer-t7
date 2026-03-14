#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-roboracer_t7}"

CID="$(docker ps -q -f "name=^/${CONTAINER_NAME}$")"
if [[ -z "${CID}" ]]; then
  echo "No running container named '${CONTAINER_NAME}'."
  exit 0
fi

echo "Stopping container ${CONTAINER_NAME} (${CID})..."
docker stop "${CID}" >/dev/null
echo "Stopped."
