#!/usr/bin/env bash
# Слить на VPS отсутствующие ключи default → user_config (как merge_user_config_missing_keys.py).
# Требует scripts/deploy.local.sh (DEPLOY_HOST, опционально DEPLOY_SSH_PORT, DEPLOY_REMOTE_DIR).
#
# Использование:
#   bash scripts/server-merge-user-config-missing-keys.sh          # dry-run (код выхода 2 если есть изменения)
#   bash scripts/server-merge-user-config-missing-keys.sh --write
#   bash scripts/server-merge-user-config-missing-keys.sh --write --restart   # + restart_processor.flag + docker restart birdlense
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
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
_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"

PY_ARGS=(--config-dir /app/app_config)
if [ "$WRITE" -eq 1 ]; then
  PY_ARGS+=(--write)
fi

set +e
ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}/app' && docker compose exec -T birdlense python3 - ${PY_ARGS[*]}" < "${ROOT}/scripts/merge_user_config_missing_keys.py"
code=$?
set -e

if [ "$WRITE" -eq 1 ] && [ "$RESTART" -eq 1 ] && [ "$code" -eq 0 ]; then
  echo "Флаг перезапуска процессора и рестарт контейнера..."
  ssh ${SSH_OPTS} "${HOST}" "mkdir -p '${REMOTE_DIR}/app/data' && printf '1' > '${REMOTE_DIR}/app/data/restart_processor.flag'"
  ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}/app' && docker restart birdlense"
fi

exit "$code"
