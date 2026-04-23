#!/usr/bin/env bash
# One-script install: Docker stack from repo root (build or pre-built image).
# Docs: docs/INSTALL.md, docs/QUICKSTART.md
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${ROOT_DIR}/app"
UI_PORT="${BIRDLENSE_PORT:-8085}"
USE_PULL=0

log() {
  printf '%s\n' "$*"
}

usage() {
  cat <<'EOF'
BirdLense Hub — install from repository root

  ./install.sh              Build images locally, create app/.env, start stack, verify
  ./install.sh --pull       Same but use pre-built ghcr.io image (no local docker build)
  ./install.sh --help       This text

Environment:
  BIRDLENSE_PORT   UI port (default 8085)

Requires: curl, openssl (for secrets). Docker / Compose v2 after bootstrap.
EOF
}

have_user_docker() {
  docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

have_sudo_docker() {
  sudo docker compose version >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1
}

ensure_docker() {
  if have_user_docker || have_sudo_docker; then
    return 0
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

  if have_user_docker || have_sudo_docker; then
    return 0
  fi

  log "Docker is installed, but current user cannot access it yet."
  log "If you just installed Docker, log out and back in, then re-run ./install.sh"
  exit 1
}

run_compose() {
  if have_user_docker; then
    (cd "${APP_DIR}" && docker compose "$@")
  elif have_sudo_docker; then
    (cd "${APP_DIR}" && sudo docker compose "$@")
  else
    log "ERROR: cannot run docker compose."
    exit 1
  fi
}

main() {
  while [[ "${1:-}" == -* ]]; do
    case "$1" in
      --pull) USE_PULL=1 ;;
      --help|-h) usage; exit 0 ;;
      *)
        log "Unknown option: $1"
        usage >&2
        exit 1
        ;;
    esac
    shift
  done

  if [[ -n "${1:-}" ]]; then
    log "Unexpected argument: $1"
    usage >&2
    exit 1
  fi

  log "BirdLense Hub — Docker install"
  ensure_docker

  if ! command -v openssl >/dev/null 2>&1; then
    log "ERROR: openssl is required (for PROCESSOR_SECRET / FLASK_SECRET_KEY in app/.env)."
    exit 1
  fi

  log "Preparing app/.env"
  bash "${APP_DIR}/scripts/setup-env.sh"

  if [[ "$USE_PULL" -eq 1 ]]; then
    log "Pulling pre-built image and starting stack"
    run_compose -f docker-compose.pull.yml pull
    run_compose -f docker-compose.pull.yml up -d
  else
    log "Building and starting Docker stack"
    run_compose up -d --build
  fi

  log "Verifying startup contract"
  "${ROOT_DIR}/scripts/verify-stack.sh" --base-url "http://127.0.0.1:${UI_PORT}"

  log ""
  log "BirdLense Hub is running."
  log "UI: http://127.0.0.1:${UI_PORT}"
  log ""
  log "Next: starter YAML (run from repo root):"
  log "  mkdir -p app/app_config && cp app/configs/minimal.yaml app/app_config/user_config.yaml"
  log "Then set Go2RTC and cameras in Settings. Details: docs/INSTALL.md"
}

main "$@"
