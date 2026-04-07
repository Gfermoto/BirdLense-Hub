#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${ROOT_DIR}/app"

log() {
  printf '%s\n' "$*"
}

have_docker() {
  docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

ensure_docker() {
  if have_docker; then
    return
  fi

  if ! command -v docker >/dev/null 2>&1; then
    log "Docker not found. Installing Docker Engine..."
    if ! command -v sudo >/dev/null 2>&1; then
      log "ERROR: sudo is required to install Docker."
      exit 1
    fi
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh
  fi

  if have_docker; then
    return
  fi

  if sudo docker compose version >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    return
  fi

  log "Docker is installed, but current user cannot access it yet."
  log "If you just installed Docker, log out and back in, then re-run ./install.sh."
  exit 1
}

main() {
  log "BirdLense Hub Docker install"
  ensure_docker

  log "Preparing app/.env"
  make -C "${APP_DIR}" setup

  log "Building and starting Docker stack"
  if have_docker; then
    (cd "${APP_DIR}" && docker compose up -d --build)
  else
    (cd "${APP_DIR}" && sudo docker compose up -d --build)
  fi

  log "BirdLense Hub started."
  log "UI: http://127.0.0.1:8085"
}

main "$@"
