#!/usr/bin/env bash
set -euo pipefail

DOCKER_USER="${DOCKER_USER:-nabilafifahq}"
IMAGE_NAME="${IMAGE_NAME:-roboracer-t7}"
TAG="${TAG:-orbslam3-mechazo}"
PLATFORM="${PLATFORM:-}"  # optional: linux/arm64

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

FULL_IMAGE="${DOCKER_USER}/${IMAGE_NAME}:${TAG}"
DOCKERFILE="${REPO_ROOT}/docker/orbslam3_mechazo.dockerfile"

echo "=== RoboRacer T7 ORB-SLAM3 (Mechazo) image ==="
echo "Image:      ${FULL_IMAGE}"
echo "Dockerfile: ${DOCKERFILE}"
echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')"

if [[ -n "${PLATFORM}" ]]; then
  docker buildx build --platform "${PLATFORM}" \
    -f "${DOCKERFILE}" \
    -t "${FULL_IMAGE}" \
    --push \
    .
else
  docker build -f "${DOCKERFILE}" -t "${FULL_IMAGE}" .
  docker push "${FULL_IMAGE}"
fi

echo ""
echo "Done. On car:"
echo "  export IMAGE=${FULL_IMAGE}"
echo "  ./scripts/car_run.sh"
