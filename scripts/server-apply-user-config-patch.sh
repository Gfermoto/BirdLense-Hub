#!/usr/bin/env bash
# Применить произвольный YAML-патч к user_config на сервере (volume app_config).
# Требует scripts/deploy.local.sh (не коммитится).
#
#   bash scripts/server-apply-user-config-patch.sh scripts/user-config-yolo-thresholds.partial.yaml
#   bash scripts/server-apply-user-config-patch.sh scripts/user-config-yolo-thresholds.partial.yaml --write
#   bash scripts/server-apply-user-config-patch.sh scripts/user-config-yolo-thresholds.partial.yaml --write --restart
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ $# -lt 1 ]; then
  echo "Использование: $0 <patch.yaml> [--write] [--restart]" >&2
  exit 1
fi
PATCH_LOCAL="$(realpath "$1")"
shift
if [ ! -f "${PATCH_LOCAL}" ]; then
  echo "Нет файла: ${PATCH_LOCAL}" >&2
  exit 1
fi
if [ ! -f "${ROOT}/scripts/deploy.local.sh" ]; then
  echo "Создайте scripts/deploy.local.sh из scripts/deploy.local.sh.example" >&2
  exit 1
fi
# shellcheck source=deploy.local.sh
. "${ROOT}/scripts/deploy.local.sh"

WRITE=0
RESTART=0
for a in "$@"; do
  case "$a" in
    --write) WRITE=1 ;;
    --restart) RESTART=1 ;;
    *) echo "Неизвестный аргумент: $a" >&2; exit 1 ;;
  esac
done

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
PATCH_BASENAME="$(basename "${PATCH_LOCAL}")"
PATCH_REMOTE="${REMOTE_DIR}/app/app_config/.patch-${PATCH_BASENAME}"
_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"
_SCP_OPTS=(-o ServerAliveInterval=30 -o ServerAliveCountMax=60)
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _SCP_OPTS=(-P "${DEPLOY_SSH_PORT}" "${_SCP_OPTS[@]}")
fi

scp "${_SCP_OPTS[@]}" "${PATCH_LOCAL}" "${HOST}:${PATCH_REMOTE}"

PY_ARGS=(--config-dir /app/app_config --patch "/app/app_config/.patch-${PATCH_BASENAME}")
if [ "$WRITE" -eq 1 ]; then
  PY_ARGS+=(--write)
fi

set +e
ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}/app' && docker compose exec -T birdlense python3 - ${PY_ARGS[*]}" < "${ROOT}/scripts/apply_user_config_patch.py"
code=$?
set -e

if [ "$WRITE" -eq 1 ] && [ "$RESTART" -eq 1 ] && [ "$code" -eq 0 ]; then
  echo "Перезапуск процессора: флаг + docker restart birdlense..."
  ssh ${SSH_OPTS} "${HOST}" "mkdir -p '${REMOTE_DIR}/app/data' && printf '1' > '${REMOTE_DIR}/app/data/restart_processor.flag'"
  ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}/app' && docker restart birdlense"
fi

exit "$code"
