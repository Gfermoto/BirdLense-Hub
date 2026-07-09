#!/usr/bin/env bash
# Resolve BIRDLENSE_PLATFORM and compose/dockerfile hints — Orin only.
# Source from deploy.sh or Makefile (do not execute standalone).
set -euo pipefail

birdlense_normalize_platform() {
  local raw="${1:-${BIRDLENSE_PLATFORM:-orin}}"
  raw="${raw//-/_}"
  case "${raw}" in
    orin | "") echo "orin" ;;
    *)
      echo "ERROR: unknown BIRDLENSE_PLATFORM=${raw} (only orin is supported)" >&2
      return 1
      ;;
  esac
}

birdlense_platform_is_jetson() {
  # Always true on Orin — NVIDIA Jetson platform
  [[ "$(birdlense_normalize_platform "${1:-}")" == "orin" ]]
}

birdlense_platform_compose_files() {
  echo "docker-compose.yml docker-compose.orin.yml"
}

birdlense_platform_dockerfile() {
  echo "app/Dockerfile"
}

birdlense_platform_profile_dir() {
  echo "app"
}
