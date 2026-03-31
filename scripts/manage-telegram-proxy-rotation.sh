#!/usr/bin/env bash
# Управление автоподбором Telegram SOCKS5-прокси через cron на сервере.
# Команды:
#   ./scripts/manage-telegram-proxy-rotation.sh install
#   ./scripts/manage-telegram-proxy-rotation.sh status
#   ./scripts/manage-telegram-proxy-rotation.sh remove
set -euo pipefail

ACTION="${1:-status}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
SSH_PORT="${DEPLOY_SSH_PORT:-22}"
SSH_OPTS="-p ${SSH_PORT} -o ServerAliveInterval=30 -o ServerAliveCountMax=20"

# По умолчанию каждые 6 часов, в начале часа
SCHEDULE="${PROXY_ROTATE_SCHEDULE:-0 */6 * * *}"
LOG_FILE="${PROXY_ROTATE_LOG:-/var/log/birdlense-telegram-proxy-rotate.log}"
CRON_MARKER="# birdlense-telegram-proxy-rotate"
CRON_CMD="cd ${REMOTE_DIR} && BIRDLENSE_PROXY_LOCAL='1' TOP_N='40' MAX_TIME='12' ./scripts/refresh-telegram-proxy.sh >> ${LOG_FILE} 2>&1"
CRON_LINE="${SCHEDULE} ${CRON_CMD} ${CRON_MARKER}"

case "${ACTION}" in
  install)
    echo "=== Install Telegram proxy rotation on ${HOST} ==="
    ssh ${SSH_OPTS} "${HOST}" "touch '${LOG_FILE}' && chmod 644 '${LOG_FILE}'"
    ssh ${SSH_OPTS} "${HOST}" "crontab -l 2>/dev/null | grep -v '${CRON_MARKER#\# }' > /tmp/birdlense.cron || true; echo \"${CRON_LINE}\" >> /tmp/birdlense.cron; crontab /tmp/birdlense.cron; rm -f /tmp/birdlense.cron"
    echo "Installed cron schedule: ${SCHEDULE}"
    ;;
  status)
    echo "=== Telegram proxy rotation status on ${HOST} ==="
    ssh ${SSH_OPTS} "${HOST}" "crontab -l 2>/dev/null | grep '${CRON_MARKER#\# }' || echo 'not installed'"
    ssh ${SSH_OPTS} "${HOST}" "test -f '${LOG_FILE}' && echo 'log:' '${LOG_FILE}' && tail -n 20 '${LOG_FILE}' || true"
    ;;
  remove)
    echo "=== Remove Telegram proxy rotation on ${HOST} ==="
    ssh ${SSH_OPTS} "${HOST}" "crontab -l 2>/dev/null | grep -v '${CRON_MARKER#\# }' > /tmp/birdlense.cron || true; crontab /tmp/birdlense.cron 2>/dev/null || crontab -r; rm -f /tmp/birdlense.cron"
    echo "Removed cron entry (if existed)."
    ;;
  *)
    echo "Usage: $0 {install|status|remove}" >&2
    exit 2
    ;;
esac
