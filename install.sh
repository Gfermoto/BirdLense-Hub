#!/usr/bin/env bash
# BirdLense Hub interactive installer/manager.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${ROOT_DIR}/app"
MODE="install"
DRY_RUN=0
USE_PULL=0
NON_INTERACTIVE=0
UI_PORT="${BIRDLENSE_PORT:-8085}"
DATA_DIR="${APP_DIR}/data"
GPU_PROFILE="${BIRDLENSE_PROFILE:-cpu}"
BACKUP_PATH="${ROOT_DIR}/birdlense-backup-$(date +%Y%m%d_%H%M%S).tgz"
RESTORE_PATH=""

log() { printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
BirdLense Hub installer

Usage:
  ./install.sh [--pull] [--dry-run] [--yes] [--port N] [--data-dir PATH] [--gpu cpu|intel|nvidia]
  ./install.sh --update [--pull] [--dry-run]
  ./install.sh --uninstall [--dry-run]
  ./install.sh --backup [--backup-file PATH]
  ./install.sh --restore --restore-file PATH

Modes:
  --update       Pull/build and recreate stack, then verify
  --uninstall    Stop and remove BirdLense containers/network
  --backup       Archive app/.env + app/app_config + app/data/db + app/data/recordings
  --restore      Restore backup archive into app/
  --dry-run      Print actions only, no changes
  --pull         Use prebuilt image path (docker-compose.pull.yml)
  --yes          Non-interactive mode (use CLI/env defaults)
  --help, -h     Show help
EOF
}

run_cmd() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] $*"
    return 0
  fi
  "$@"
}

have_user_docker() {
  docker compose version >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

have_sudo_docker() {
  command -v sudo >/dev/null 2>&1 &&
    sudo docker compose version >/dev/null 2>&1 &&
    sudo docker info >/dev/null 2>&1
}

docker_prefix() {
  if have_user_docker; then
    printf '%s' ""
  elif have_sudo_docker; then
    printf '%s' "sudo "
  else
    die "Docker доступен, но текущий пользователь не может выполнять docker compose."
  fi
}

run_compose() {
  local prefix
  prefix="$(docker_prefix)"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] (cd ${APP_DIR} && BIRDLENSE_PORT=${UI_PORT} ${prefix}docker compose $*)"
    return 0
  fi
  if [[ -z "${prefix}" ]]; then
    (cd "${APP_DIR}" && BIRDLENSE_PORT="${UI_PORT}" docker compose "$@")
  else
    (cd "${APP_DIR}" && sudo BIRDLENSE_PORT="${UI_PORT}" docker compose "$@")
  fi
}

detect_platform() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  case "${os}" in
    linux|darwin) ;;
    *) die "Unsupported OS: ${os}. Supported: linux, darwin." ;;
  esac
  case "${arch}" in
    x86_64|amd64|aarch64|arm64) ;;
    *) warn "Unknown architecture ${arch}; continuing cautiously." ;;
  esac
  log "Platform: os=${os}, arch=${arch}"
}

ensure_docker() {
  if have_user_docker || have_sudo_docker; then
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    if [[ "$(uname -s)" == "Linux" ]]; then
      log "Docker not found. Installing via get.docker.com ..."
      command -v curl >/dev/null 2>&1 || die "curl is required to install Docker."
      command -v sudo >/dev/null 2>&1 || die "sudo is required to install Docker."
      run_cmd curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
      run_cmd sudo sh /tmp/get-docker.sh
      run_cmd rm -f /tmp/get-docker.sh
    else
      die "Docker is not installed. On macOS install Docker Desktop first."
    fi
  fi
  have_user_docker || have_sudo_docker || die "Docker still unavailable after setup."
}

validate_port() {
  [[ "${UI_PORT}" =~ ^[0-9]+$ ]] || die "Port must be numeric."
  (( UI_PORT >= 1024 && UI_PORT <= 65535 )) || die "Port must be in 1024..65535."
}

validate_gpu() {
  case "${GPU_PROFILE}" in
    cpu|intel|nvidia) ;;
    *) die "Unsupported GPU profile: ${GPU_PROFILE}. Use cpu|intel|nvidia." ;;
  esac
}

interactive_wizard() {
  [[ "${NON_INTERACTIVE}" -eq 1 ]] && return 0
  log ""
  log "Interactive setup (press Enter to keep defaults)."
  read -r -p "UI port [${UI_PORT}]: " ans_port
  [[ -n "${ans_port}" ]] && UI_PORT="${ans_port}"
  read -r -p "Data directory [${DATA_DIR}]: " ans_data
  [[ -n "${ans_data}" ]] && DATA_DIR="${ans_data}"
  read -r -p "GPU profile cpu|intel|nvidia [${GPU_PROFILE}]: " ans_gpu
  [[ -n "${ans_gpu}" ]] && GPU_PROFILE="${ans_gpu}"
  read -r -p "Use prebuilt image (--pull) y/N: " ans_pull
  case "${ans_pull:-N}" in
    y|Y|yes|YES) USE_PULL=1 ;;
  esac
}

ensure_secrets() {
  command -v openssl >/dev/null 2>&1 || die "openssl is required."
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] setup app/.env + secrets"
    return 0
  fi
  BIRDLENSE_PORT="${UI_PORT}" bash "${APP_DIR}/scripts/setup-env.sh"
}

write_profile_env() {
  local profile_file="${APP_DIR}/env/profiles/${GPU_PROFILE}.env"
  [[ -f "${profile_file}" ]] || return 0
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] apply profile env from ${profile_file}"
    return 0
  fi
  while IFS= read -r line; do
    [[ -z "${line}" ]] && continue
    [[ "${line}" == \#* ]] && continue
    local key="${line%%=*}"
    local val="${line#*=}"
    if grep -q "^${key}=" "${APP_DIR}/.env"; then
      sed -i "s|^${key}=.*|${key}=${val}|" "${APP_DIR}/.env"
    else
      printf '%s=%s\n' "${key}" "${val}" >> "${APP_DIR}/.env"
    fi
  done < "${profile_file}"
}

update_data_dir_env() {
  local abs_data
  abs_data="$(cd "$(dirname "${DATA_DIR}")" && pwd)/$(basename "${DATA_DIR}")"
  run_cmd mkdir -p "${abs_data}"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] set BIRDLENSE_DATA_DIR=${abs_data} in app/.env"
    return 0
  fi
  if grep -q '^BIRDLENSE_DATA_DIR=' "${APP_DIR}/.env"; then
    sed -i "s|^BIRDLENSE_DATA_DIR=.*|BIRDLENSE_DATA_DIR=${abs_data}|" "${APP_DIR}/.env"
  else
    printf '\nBIRDLENSE_DATA_DIR=%s\n' "${abs_data}" >> "${APP_DIR}/.env"
  fi
}

healthcheck() {
  log "Health check..."
  local verify="${ROOT_DIR}/scripts/public/verify-stack.sh"
  [[ -x "${verify}" ]] || verify="${ROOT_DIR}/scripts/verify-stack.sh"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] ${verify} --base-url http://127.0.0.1:${UI_PORT}"
    return 0
  fi
  "${verify}" --base-url "http://127.0.0.1:${UI_PORT}"
}

do_install_or_update() {
  detect_platform
  ensure_docker
  validate_port
  validate_gpu
  interactive_wizard
  validate_port
  validate_gpu
  ensure_secrets
  update_data_dir_env
  write_profile_env

  if [[ "${USE_PULL}" -eq 1 ]]; then
    run_compose -f docker-compose.pull.yml pull
    run_compose -f docker-compose.pull.yml up -d
  else
    run_compose up -d --build
  fi
  healthcheck
  log ""
  log "BirdLense Hub is ready."
  log "UI: http://127.0.0.1:${UI_PORT}"
  log "Logs: make logs"
  log "Config: app/.env, app/app_config/user_config.yaml"
}

do_uninstall() {
  ensure_docker
  run_compose down --remove-orphans
  log "BirdLense containers stopped and removed."
}

do_backup() {
  run_cmd mkdir -p "$(dirname "${BACKUP_PATH}")"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] tar -czf ${BACKUP_PATH} app/.env app/app_config app/data/db app/data/recordings"
    return 0
  fi
  tar -czf "${BACKUP_PATH}" \
    -C "${ROOT_DIR}" \
    app/.env app/app_config app/data/db app/data/recordings
  log "Backup created: ${BACKUP_PATH}"
}

do_restore() {
  [[ -n "${RESTORE_PATH}" ]] || die "--restore-file is required for --restore."
  [[ -f "${RESTORE_PATH}" ]] || die "Restore archive not found: ${RESTORE_PATH}"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "[dry-run] restore ${RESTORE_PATH} into ${ROOT_DIR}"
    return 0
  fi
  tar -xzf "${RESTORE_PATH}" -C "${ROOT_DIR}"
  log "Restore completed from ${RESTORE_PATH}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h) usage; exit 0 ;;
      --pull) USE_PULL=1 ;;
      --yes) NON_INTERACTIVE=1 ;;
      --dry-run) DRY_RUN=1 ;;
      --uninstall) MODE="uninstall" ;;
      --update) MODE="update" ;;
      --backup) MODE="backup" ;;
      --restore) MODE="restore" ;;
      --port) shift; UI_PORT="${1:-}";;
      --data-dir) shift; DATA_DIR="${1:-}";;
      --gpu) shift; GPU_PROFILE="${1:-}";;
      --backup-file) shift; BACKUP_PATH="${1:-}";;
      --restore-file) shift; RESTORE_PATH="${1:-}";;
      *) die "Unknown option: $1" ;;
    esac
    shift
  done
}

main() {
  parse_args "$@"
  case "${MODE}" in
    install|update) do_install_or_update ;;
    uninstall) do_uninstall ;;
    backup) do_backup ;;
    restore) do_restore ;;
    *) die "Unsupported mode: ${MODE}" ;;
  esac
}

main "$@"
