#!/usr/bin/env bash
# BIRDLENSE_PLATFORM — Orin-only.
set -euo pipefail

birdlense_normalize_platform() {
  local raw="${1:-${BIRDLENSE_PLATFORM:-orin}}"
  raw="${raw//-/_}"
  case "${raw}" in
    orin | "") echo "orin" ;;
    *)
      echo "ERROR: BIRDLENSE_PLATFORM=${raw} — only orin is supported" >&2
      return 1
      ;;
  esac
}

birdlense_platform_is_jetson() {
  return 1
}

birdlense_platform_is_orin() {
  return 0
}

birdlense_platform_compose_files() {
  echo "docker-compose.yml docker-compose.orin.yml"
}

birdlense_platform_dockerfile() {
  echo "app/Dockerfile.orin"
}

birdlense_platform_profile_dir() {
  echo "deploy/profiles/orin"
}
