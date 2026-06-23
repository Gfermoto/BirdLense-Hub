#!/usr/bin/env bash
# Resolve BIRDLENSE_PLATFORM and compose/dockerfile hints.
# Source from deploy.sh or Makefile (do not execute standalone).
set -euo pipefail

birdlense_normalize_platform() {
  local raw="${1:-${BIRDLENSE_PLATFORM:-jetson_nano}}"
  raw="${raw//-/_}"
  case "${raw}" in
    intel_nuc | "") echo "intel_nuc" ;;
    jetson_nano) echo "jetson_nano" ;;
    *)
      echo "ERROR: unknown BIRDLENSE_PLATFORM=${raw} (use intel_nuc or jetson_nano)" >&2
      return 1
      ;;
  esac
}

birdlense_platform_is_jetson() {
  [[ "$(birdlense_normalize_platform "${1:-}")" == "jetson_nano" ]]
}

birdlense_platform_compose_files() {
  if birdlense_platform_is_jetson; then
    echo "docker-compose.yml docker-compose.jetson.yml"
  else
    echo "docker-compose.yml"
  fi
}

birdlense_platform_dockerfile() {
  if birdlense_platform_is_jetson; then
    echo "app/Dockerfile.jetson"
  else
    echo "app/Dockerfile"
  fi
}

birdlense_platform_profile_dir() {
  local p
  p="$(birdlense_normalize_platform)"
  case "${p}" in
    intel_nuc) echo "deploy/profiles/intel-nuc" ;;
    jetson_nano) echo "deploy/profiles/jetson-nano" ;;
  esac
}
