#!/usr/bin/env bash
# Build and push the combined race image: EKF, SLAM/Cartographer, Cyclone, raceline stack, manual map, TUM.
#
# Local native build (same arch as host):
#   ./scripts/docker_build_full_stack.sh
#
# Raspberry Pi (linux/arm64) from Mac — buildx emulated ARM + push:
#   PLATFORM=linux/arm64 ./scripts/docker_build_full_stack.sh
#   # or:
#   ./scripts/docker_buildx_arm64.sh
set -euo pipefail

DOCKER_USER="${DOCKER_USER:-nabilafifahq}"
IMAGE_NAME="${IMAGE_NAME:-roboracer-t7}"
TAG="${TAG:-full-stack}"
PLATFORM="${PLATFORM:-}"  # set to linux/arm64 for Pi push-from-Mac via buildx
BUILDER="${BUILDER:-roboracer-buildx}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

FULL_IMAGE="${DOCKER_USER}/${IMAGE_NAME}:${TAG}"
DOCKERFILE="${REPO_ROOT}/docker/dockerfile"

echo "=== RoboRacer T7 full-stack image ==="
echo "Image:  ${FULL_IMAGE}"
echo "Dockerfile: ${DOCKERFILE}"
echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
echo ""

if [[ -n "${PLATFORM}" ]]; then
  echo "buildx --platform ${PLATFORM} --push"
  if ! docker buildx inspect "${BUILDER}" >/dev/null 2>&1; then
    echo "Creating buildx builder '${BUILDER}'..."
    docker buildx create --name "${BUILDER}" --driver docker-container --bootstrap
  fi
  docker buildx use "${BUILDER}"
  docker buildx build --platform "${PLATFORM}" \
    -f "${DOCKERFILE}" \
    -t "${FULL_IMAGE}" \
    --progress=plain \
    --push \
    .
  echo ""
  echo "Remote digest (imagetools):"
  docker buildx imagetools inspect "${FULL_IMAGE}" 2>/dev/null | head -n 15 || true
else
  echo "docker build (local platform)"
  docker build -f "${DOCKERFILE}" -t "${FULL_IMAGE}" .
  echo "docker push"
  docker push "${FULL_IMAGE}"
  echo ""
  echo "Digest:"
  docker inspect "${FULL_IMAGE}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true
fi

echo ""
echo "On the car (arm64 Pi):"
echo "  docker pull ${FULL_IMAGE}"
echo "  export IMAGE=${FULL_IMAGE}"
echo "  ./scripts/car_run.sh"
