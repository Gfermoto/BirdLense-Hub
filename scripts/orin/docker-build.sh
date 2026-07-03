#!/usr/bin/env bash
# Orin image build on Jetson (L4T apt via dpkg-deb -x, no docker build --privileged).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE_TAG="${ORIN_IMAGE_TAG:-app-birdlense:latest}"

echo "Orin docker build (L4T r39.2 GStreamer in-image via dpkg-deb -x)..."
DOCKER_BUILDKIT=0 docker build \
  -f "${REPO_ROOT}/app/Dockerfile.orin" \
  -t "${IMAGE_TAG}" \
  "${REPO_ROOT}"
echo "Built ${IMAGE_TAG}"
