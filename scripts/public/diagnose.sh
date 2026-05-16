#!/bin/bash
# Диагностика перезапусков и подвисаний BirdLense
# Запуск: make diagnose или ./scripts/diagnose.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/../deploy.local.sh" ] && . "${SCRIPT_DIR}/../deploy.local.sh"
HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"

echo "=== Диагностика BirdLense на ${HOST} ==="
echo ""

echo "1. Статус контейнера и время работы:"
ssh ${SSH_OPTS} "${HOST}" "docker ps -a --filter name=birdlense --format 'Status: {{.Status}}\nStarted: {{.RunningFor}}' 2>/dev/null || echo 'Контейнер не найден'"
echo ""

echo "2. Exit code последнего выхода (137=OOM, 139=segfault, 0=норма):"
ssh ${SSH_OPTS} "${HOST}" "docker inspect birdlense --format 'ExitCode: {{.State.ExitCode}}' 2>/dev/null || echo 'N/A'"
echo ""

echo "3. Память (host + контейнер):"
ssh ${SSH_OPTS} "${HOST}" "echo 'Host:'; free -h | head -2; echo ''; echo 'Container:'; docker stats birdlense --no-stream 2>/dev/null || echo 'N/A'"
echo ""

echo "4. Restart flag (если есть — процессор выйдет при следующей итерации):"
ssh ${SSH_OPTS} "${HOST}" "ls -la ${REMOTE_DIR}/app/data/restart_processor.flag 2>/dev/null || echo 'Нет'"
echo ""

echo "5. Рестарты за последний час (docker events, таймаут 3 сек):"
ssh ${SSH_OPTS} "${HOST}" "timeout 3 docker events --since 1h --filter 'container=birdlense' --filter 'event=restart' --format '{{.Time}} restart' 2>/dev/null | tail -15 || echo 'Нет или таймаут'"
echo ""

echo "6. Последние 80 строк логов:"
ssh ${SSH_OPTS} "${HOST}" "docker logs birdlense --tail 80 2>&1"
echo ""
echo "=== Конец. Подробнее: docs/user/troubleshooting.md (EN) / docs/ru/troubleshooting.ru.md ==="
