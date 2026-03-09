#!/bin/bash
# Деплой BirdLense
# Локальные настройки (IP, URL) — в scripts/deploy.local.sh (не коммитить)
# Критично: НЕ перезаписываем data и app_config на сервере

set -e

# Загрузить локальные переопределения (создайте из deploy.local.sh.example)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
DEPLOY_URL="${DEPLOY_URL:-http://localhost:8085}"
echo "=== Деплой BirdLense на ${HOST} ==="

# 0. Удаление старых контейнеров (nginx, processor, web, ntfy)
echo "0. Остановка старых контейнеров..."
ssh "${HOST}" "docker stop birdlense_nginx birdlense_processor birdlense_web birdlense_ntfy 2>/dev/null || true; docker rm birdlense_nginx birdlense_processor birdlense_web birdlense_ntfy 2>/dev/null || true"

# 1. Синхронизация кода
# БЕЗ app/data (recordings, db). БЕЗ app_config/user_config.yaml (настройки на сервере)
echo "1. Синхронизация кода..."
cd "$(dirname "$0")/.."
tar --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='.env' \
    --exclude='app/data' \
    --exclude='app/app_config/user_config.yaml' \
    --exclude='scripts/deploy.local.sh' \
    -czf - . | ssh "${HOST}" "mkdir -p ${REMOTE_DIR} && cd ${REMOTE_DIR} && tar -xzf -"

# 1.5 MCP_TOKEN в app/.env (если задан в deploy.local.sh)
if [ -n "${MCP_TOKEN:-}" ]; then
  echo "1.5 Запись MCP_TOKEN в app/.env на сервере..."
  ssh "${HOST}" "mkdir -p ${REMOTE_DIR}/app && \
    (grep -v '^MCP_TOKEN=' ${REMOTE_DIR}/app/.env 2>/dev/null || true; echo 'MCP_TOKEN=${MCP_TOKEN}') > ${REMOTE_DIR}/app/.env.new && \
    mv ${REMOTE_DIR}/app/.env.new ${REMOTE_DIR}/app/.env"
fi

# 2. Сборка и запуск
echo "2. Сборка и запуск..."
ssh "${HOST}" "mkdir -p ${REMOTE_DIR}/app/data/recordings ${REMOTE_DIR}/app/data/db ${REMOTE_DIR}/app/app_config && cd ${REMOTE_DIR}/app && make stop 2>/dev/null; make build && make start"

# 3. Проверка после деплоя
echo ""
echo "3. Проверка после деплоя..."
sleep 8
echo "  - Docker logs (последние 25 строк):"
ssh "${HOST}" "docker logs birdlense --tail=25 2>&1" | tail -30
echo ""
echo "  - API health:"
curl -sf "${DEPLOY_URL}/api/ui/health" >/dev/null && echo "    OK" || echo "    FAIL (проверьте ${DEPLOY_URL})"
echo "  - API cameras:"
cameras=$(curl -sf "${DEPLOY_URL}/api/ui/cameras" 2>/dev/null | head -c 150) && echo "    ${cameras}..." || echo "    (не доступен)"
echo ""
echo "=== Готово. UI: ${DEPLOY_URL} ==="
echo "Настройки и записи на сервере не тронуты."
echo ""
echo "Если API недоступен из браузера: добавьте на сервере в app/.env:"
echo "  CORS_ORIGINS=${DEPLOY_URL}"
