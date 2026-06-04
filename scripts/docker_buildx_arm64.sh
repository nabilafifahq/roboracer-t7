#!/usr/bin/env bash
# Build RoboRacer T7 full-stack image for Raspberry Pi (linux/arm64) on Mac via Docker buildx.
#
# Docker Desktop on Apple Silicon: emulated ARM build when host is arm64; on Intel Mac, QEMU emulates arm64.
# Output is pushed to Docker Hub (--push). Pi pulls the same tag.
#
# Usage (from repo root):
#   export DOCKER_USER=your_dockerhub_user   # required for your own image
#   docker login
#   ./scripts/docker_buildx_arm64.sh
#
# Optional:
#   TAG=full-stack-cartographer ./scripts/docker_buildx_arm64.sh
#   LOAD=1 ./scripts/docker_buildx_arm64.sh    # --load into local docker (arm64 only; slow on Intel Mac)
#   PUSH=0 LOAD=1 ./scripts/docker_buildx_arm64.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

DOCKER_USER="${DOCKER_USER:-nabilafifahq}"
IMAGE_NAME="${IMAGE_NAME:-roboracer-t7}"
TAG="${TAG:-cartographer-ekf-arm64}"
PLATFORM="${PLATFORM:-linux/arm64}"
BUILDER="${BUILDER:-roboracer-buildx}"
DOCKERFILE="${REPO_ROOT}/docker/dockerfile"
FULL_IMAGE="${DOCKER_USER}/${IMAGE_NAME}:${TAG}"

# Default: push to Hub (Pi cannot use --load on Mac for a different arch without load)
PUSH="${PUSH:-1}"
LOAD="${LOAD:-0}"

if [[ "${PUSH}" == "1" && "${LOAD}" == "1" ]]; then
  echo "ERROR: Set only one of PUSH=1 or LOAD=1 (buildx cannot --push and --load together)." >&2
  exit 1
fi

echo "=== RoboRacer T7 buildx (ARM64 for Pi) ==="
echo "Image:     ${FULL_IMAGE}"
echo "Platform:  ${PLATFORM}"
echo "Builder:   ${BUILDER}"
echo "Dockerfile: ${DOCKERFILE}"
echo "Branch:    $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') @ $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
echo ""

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Desktop for Mac." >&2
  exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
  echo "ERROR: docker buildx not available. Update Docker Desktop." >&2
  exit 1
fi

# Ensure a buildx builder that supports cross-platform / arm64
if ! docker buildx inspect "${BUILDER}" >/dev/null 2>&1; then
  echo "Creating buildx builder '${BUILDER}' (docker-container driver)..."
  docker buildx create --name "${BUILDER}" --driver docker-container --bootstrap
fi
docker buildx use "${BUILDER}"
docker buildx inspect --bootstrap >/dev/null

echo "Builder platforms:"
docker buildx inspect "${BUILDER}" | sed -n '/Platforms:/,/Labels:/p' | head -n 5 || true
echo ""

if [[ "${PUSH}" == "1" ]]; then
  if ! docker info 2>/dev/null | grep -q 'Username:'; then
    echo "WARN: 'docker login' may be required before --push succeeds."
  fi
fi

BUILD_ARGS=(
  build
  --platform "${PLATFORM}"
  -f "${DOCKERFILE}"
  -t "${FULL_IMAGE}"
  --progress=plain
)

if [[ "${PUSH}" == "1" ]]; then
  echo ">>> docker buildx build --push (this can take 30–90+ min on Mac; Cartographer + colcon are heavy)"
  BUILD_ARGS+=(--push)
elif [[ "${LOAD}" == "1" ]]; then
  echo ">>> docker buildx build --load (single-platform image in local docker)"
  BUILD_ARGS+=(--load)
else
  echo "ERROR: Set PUSH=1 (default) or LOAD=1" >&2
  exit 1
fi

BUILD_ARGS+=(.)

docker buildx "${BUILD_ARGS[@]}"

echo ""
echo "=== Done ==="
if [[ "${PUSH}" == "1" ]]; then
  echo "Remote image: ${FULL_IMAGE}"
  docker buildx imagetools inspect "${FULL_IMAGE}" 2>/dev/null | head -n 20 || true
  echo ""
  echo "On the Pi:"
  echo "  docker pull ${FULL_IMAGE}"
  echo "  export IMAGE=${FULL_IMAGE}"
  echo "  ./scripts/car_run.sh"
else
  echo "Loaded locally as: ${FULL_IMAGE}"
  echo "Note: arm64 image on amd64 Mac runs via emulation only; deploy to Pi with PUSH=1."
fi
