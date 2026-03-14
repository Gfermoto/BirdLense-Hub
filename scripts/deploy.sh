#!/bin/bash
# Деплой BirdLense Hub
# Локальные настройки (IP, URL) — в scripts/deploy.local.sh (не коммитить)
# Критично: НЕ перезаписываем data и app_config на сервере

set -e

# Загрузить локальные переопределения (создайте из deploy.local.sh.example)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
DEPLOY_URL="${DEPLOY_URL:-http://localhost:8085}"
# Keepalive — сборка Docker может занимать 5+ мин, без этого SSH обрывается (Broken pipe)
SSH_OPTS="-o ServerAliveInterval=30 -o ServerAliveCountMax=60"
echo "=== Деплой BirdLense Hub на ${HOST} ==="
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]] && [[ "${DEPLOY_URL}" == *"localhost"* ]]; then
  echo "ВНИМАНИЕ: DEPLOY_URL=${DEPLOY_URL} — health check будет с локальной машины. Для удалённого сервера задайте DEPLOY_URL в deploy.local.sh (например http://192.168.1.11:8085)"
fi

# 0. Остановка текущего контейнера (один контейнер birdlense)
echo "0. Остановка контейнера..."
ssh ${SSH_OPTS} "${HOST}" "docker stop birdlense 2>/dev/null || true; docker rm birdlense 2>/dev/null || true"

# 1. Синхронизация кода
# БЕЗ app/data (recordings, db). БЕЗ app_config/user_config.yaml (настройки на сервере)
echo "1. Синхронизация кода..."
cd "$(dirname "$0")/.."
tar --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='.env' \
    --exclude='app/data' \
    --exclude='app/app_config/user_config.yaml' \
    --exclude='scripts/deploy.local.sh' \
    -czf - . | ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR} && cd ${REMOTE_DIR} && tar -xzf -"

# 1.5 Секреты в app/.env
# PROCESSOR_SECRET — всегда задаём (генерируем при отсутствии)
if [ -z "${PROCESSOR_SECRET:-}" ]; then
  PROCESSOR_SECRET=$(openssl rand -hex 16)
  echo "1.5 PROCESSOR_SECRET сгенерирован. Добавьте в deploy.local.sh: export PROCESSOR_SECRET='${PROCESSOR_SECRET}'"
fi
if [ -n "${MCP_TOKEN:-}" ] || [ -n "${PROCESSOR_SECRET:-}" ]; then
  echo "1.5 Запись секретов в app/.env на сервере..."
  # Копируем .env.example если .env отсутствует или повреждён (>1MB)
  ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app && \
    SIZE=\$(stat -c%s ${REMOTE_DIR}/app/.env 2>/dev/null || echo 0); \
    if [ ! -f ${REMOTE_DIR}/app/.env ] || [ \"\$SIZE\" -gt 1048576 ]; then \
      cp ${REMOTE_DIR}/app/.env.example ${REMOTE_DIR}/app/.env 2>/dev/null || true; \
    fi"
  # Безопасная запись: printf экранирует спецсимволы в секретах
  ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app && \
    (grep -v '^MCP_TOKEN=' ${REMOTE_DIR}/app/.env 2>/dev/null || true; \
     grep -v '^PROCESSOR_SECRET=' ${REMOTE_DIR}/app/.env 2>/dev/null || true; \
     [ -n \"${MCP_TOKEN:-}\" ] && printf 'MCP_TOKEN=%s\n' \"${MCP_TOKEN}\"; \
     printf 'PROCESSOR_SECRET=%s\n' \"${PROCESSOR_SECRET}\") > ${REMOTE_DIR}/app/.env.new && \
    mv ${REMOTE_DIR}/app/.env.new ${REMOTE_DIR}/app/.env"
fi

# 2. Сборка и запуск
echo "2. Сборка и запуск..."
ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app/data/recordings ${REMOTE_DIR}/app/data/db ${REMOTE_DIR}/app/app_config && cd ${REMOTE_DIR}/app && make stop 2>/dev/null; make build && make start"

# 3. Проверка после деплоя
echo ""
echo "3. Проверка после деплоя..."
sleep 8
echo "  - Docker logs (последние 25 строк):"
ssh ${SSH_OPTS} "${HOST}" "docker logs birdlense --tail=25 2>&1" | tail -30
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
