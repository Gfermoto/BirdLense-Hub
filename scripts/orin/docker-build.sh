#!/usr/bin/env bash
# Orin image build on Jetson: L4T apt via selective deb extract (ar + tar).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE_TAG="${ORIN_IMAGE_TAG:-app-birdlense:latest}"

echo "Orin docker build (L4T r39.2 GStreamer native)..."
DOCKER_BUILDKIT=0 docker build \
  -f "${REPO_ROOT}/app/Dockerfile.orin" \
  -t "${IMAGE_TAG}" \
  "${REPO_ROOT}"
echo "Built ${IMAGE_TAG}"
