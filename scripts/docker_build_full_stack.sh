#!/usr/bin/env bash
# Build and push the combined race image: EKF, SLAM, Cyclone, Derek Nav2 raceline, manual map, TUM.
set -euo pipefail

DOCKER_USER="${DOCKER_USER:-nabilafifahq}"
IMAGE_NAME="${IMAGE_NAME:-roboracer-t7}"
TAG="${TAG:-full-stack}"
PLATFORM="${PLATFORM:-}"  # set to linux/arm64 for Pi push-from-Mac via buildx

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
  echo "buildx push --platform ${PLATFORM}"
  docker buildx build --platform "${PLATFORM}" \
    -f "${DOCKERFILE}" \
    -t "${FULL_IMAGE}" \
    --push \
    .
else
  echo "docker build (local platform)"
  docker build -f "${DOCKERFILE}" -t "${FULL_IMAGE}" .
  echo "docker push"
  docker push "${FULL_IMAGE}"
fi

echo ""
echo "Done. Digest:"
docker inspect "${FULL_IMAGE}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true
echo ""
echo "On the car:"
echo "  docker pull ${FULL_IMAGE}"
echo "  export IMAGE=${FULL_IMAGE}"
echo "  ./scripts/car_run.sh"
