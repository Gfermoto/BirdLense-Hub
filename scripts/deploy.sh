#!/bin/bash
# Деплой BirdLense Hub
# Локальные настройки (IP, URL) — в scripts/deploy.local.sh (не коммитить)
# Критично: НЕ перезаписываем data и app_config на сервере
# Сам следит и исправляет: rsync на сервере, повтор при сбоях

set -e

# Загрузить локальные переопределения (создайте из deploy.local.sh.example)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
DEPLOY_URL="${DEPLOY_URL:-http://localhost:8085}"
SYNC_RETRIES="${SYNC_RETRIES:-3}"
# Keepalive — сборка Docker может занимать 5+ мин, без этого SSH обрывается (Broken pipe)
SSH_OPTS="-o ServerAliveInterval=30 -o ServerAliveCountMax=60"
echo "=== Деплой BirdLense Hub на ${HOST} ==="
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]] && [[ "${DEPLOY_URL}" == *"localhost"* ]]; then
  echo "ВНИМАНИЕ: DEPLOY_URL=${DEPLOY_URL} — health check будет с локальной машины. Для удалённого сервера задайте DEPLOY_URL в deploy.local.sh (например http://192.168.1.11:8085)"
fi

# 0. Остановка текущего контейнера (один контейнер birdlense)
echo "0. Остановка контейнера..."
ssh ${SSH_OPTS} "${HOST}" "docker stop birdlense 2>/dev/null || true; docker rm birdlense 2>/dev/null || true"

# 0.5. Убедиться, что rsync есть на сервере (для надёжной синхронизации)
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  if ! ssh ${SSH_OPTS} "${HOST}" "which rsync" 2>/dev/null; then
    echo "0.5. Установка rsync на сервере..."
    ssh ${SSH_OPTS} "${HOST}" "apt-get update -qq && apt-get install -y rsync"
  fi
fi

# 1. Синхронизация кода (rsync устойчивее к обрывам, повтор при сбое)
# БЕЗ app/data (recordings, db). БЕЗ app_config/user_config.yaml (настройки на сервере)
echo "1. Синхронизация кода..."
cd "$(dirname "$0")/.."
RSYNC_EXCLUDES="--exclude=.git --exclude=node_modules --exclude=__pycache__ --exclude=.env"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/data --exclude=app/app_config/user_config.yaml --exclude=scripts/deploy.local.sh"
sync_ok=0
for attempt in $(seq 1 ${SYNC_RETRIES}); do
  if [[ "${HOST}" == "localhost" || "${HOST}" == "127.0.0.1" ]]; then
    rsync -a --delete ${RSYNC_EXCLUDES} ./ "${REMOTE_DIR}/" && sync_ok=1 && break
  else
    rsync -avz --delete -e "ssh ${SSH_OPTS}" ${RSYNC_EXCLUDES} ./ "${HOST}:${REMOTE_DIR}/" && sync_ok=1 && break
  fi
  echo "  Попытка ${attempt}/${SYNC_RETRIES} не удалась, повтор через 5 сек..."
  sleep 5
done
if [[ $sync_ok -eq 0 ]]; then
  echo "Ошибка: синхронизация не удалась после ${SYNC_RETRIES} попыток"
  exit 1
fi

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

# 2. Сборка и запуск (повтор при сбое — Docker pull, сеть)
echo "2. Сборка и запуск..."
BUILD_RETRIES="${BUILD_RETRIES:-2}"
build_ok=0
for attempt in $(seq 1 ${BUILD_RETRIES}); do
  if ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app/data/recordings ${REMOTE_DIR}/app/data/db ${REMOTE_DIR}/app/app_config && cd ${REMOTE_DIR}/app && make stop 2>/dev/null; make build && make start"; then
    build_ok=1
    break
  fi
  echo "  Сборка/запуск попытка ${attempt}/${BUILD_RETRIES} не удалась, повтор через 10 сек..."
  sleep 10
done
if [[ $build_ok -eq 0 ]]; then
  echo "Ошибка: сборка/запуск не удались после ${BUILD_RETRIES} попыток"
  exit 1
fi

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
