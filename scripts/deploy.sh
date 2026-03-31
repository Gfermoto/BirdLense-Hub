#!/bin/bash
# Деплой BirdLense Hub
# Локальные настройки (IP, URL) — в scripts/deploy.local.sh (не коммитить)
# Критично: не трогаем recordings/db/dataset в app/data; статические images синхронизируем. user_config не перезаписываем.
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
# Порт через DEPLOY_SSH_PORT (по умолчанию 22)
_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"
echo "=== Деплой BirdLense Hub на ${HOST} ==="
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]] && [[ "${DEPLOY_URL}" == *"localhost"* ]]; then
  echo "ВНИМАНИЕ: DEPLOY_URL=${DEPLOY_URL} — health check будет с локальной машины. Для удалённого сервера задайте DEPLOY_URL в deploy.local.sh (например http://YOUR_HOST:8085)"
fi

# 0. Остановка контейнера приложения (Redis birdlense-redis не удаляем — кэш переживает пересборку)
echo "0. Остановка контейнера birdlense..."
ssh ${SSH_OPTS} "${HOST}" "docker stop birdlense 2>/dev/null || true; docker rm birdlense 2>/dev/null || true"

# 0.5. Убедиться, что rsync есть на сервере (для надёжной синхронизации)
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  if ! ssh ${SSH_OPTS} "${HOST}" "which rsync" 2>/dev/null; then
    echo "0.5. Установка rsync на сервере..."
    ssh ${SSH_OPTS} "${HOST}" "apt-get update -qq && apt-get install -y rsync"
  fi
fi

# 0.9. Сборка UI локально (обход ETIMEDOUT npm на сервере)
echo "0.9. Сборка UI локально..."
cd "$(dirname "$0")/.."
(cd app/ui && npm run build) || { echo "Ошибка: сборка UI не удалась"; exit 1; }

# 1. Синхронизация кода (rsync устойчивее к обрывам, повтор при сбое)
# app/data: синхронизируем статику (images), НЕ трогаем recordings, db, dataset (тяжёлые/локальные)
echo "1. Синхронизация кода..."
RSYNC_EXCLUDES="--exclude=.git --exclude=node_modules --exclude=__pycache__ --exclude=.env"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/data/recordings --exclude=app/data/db --exclude=app/data/dataset"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/app_config/user_config.yaml --exclude=scripts/deploy.local.sh"
# Локальные venv / сборка док — не на сервер
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.venv-docs-tmp --exclude=.venv-docs --exclude=site"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/.venv --exclude=.venv-datasets"
# CodeQL CLI, БД и SARIF (scripts/codeql-local.sh) — десятки МБ/ГБ, на хаб не нужны
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.tools"
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
# Предупреждения rsync «cannot delete non-empty directory» — часто лишние каталоги на сервере вне дерева репо; при необходимости удалите вручную по SSH.

# 1.5 Секреты в app/.env
# PROCESSOR_SECRET — всегда задаём (генерируем при отсутствии)
if [ -z "${PROCESSOR_SECRET:-}" ]; then
  PROCESSOR_SECRET=$(openssl rand -hex 16)
  echo "1.5 PROCESSOR_SECRET сгенерирован. Добавьте в deploy.local.sh: export PROCESSOR_SECRET='${PROCESSOR_SECRET}'"
fi
if [ -n "${MCP_TOKEN:-}" ] || [ -n "${PROCESSOR_SECRET:-}" ] || [ -n "${FLASK_SECRET_KEY:-}" ] || [ -n "${BIRDLENSE_ENV:-}" ]; then
  echo "1.5 Запись секретов в app/.env на сервере..."
  ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app && \
    SIZE=\$(stat -c%s ${REMOTE_DIR}/app/.env 2>/dev/null || echo 0); \
    if [ ! -f ${REMOTE_DIR}/app/.env ] || [ \"\$SIZE\" -gt 1048576 ]; then \
      cp ${REMOTE_DIR}/app/.env.example ${REMOTE_DIR}/app/.env 2>/dev/null || true; \
    fi"
  ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app && \
    (grep -v -E '^(MCP_TOKEN|PROCESSOR_SECRET|FLASK_SECRET_KEY|BIRDLENSE_ENV)=' ${REMOTE_DIR}/app/.env 2>/dev/null || true; \
     [ -n \"${MCP_TOKEN:-}\" ] && printf 'MCP_TOKEN=%s\n' \"${MCP_TOKEN}\"; \
     [ -n \"${FLASK_SECRET_KEY:-}\" ] && printf 'FLASK_SECRET_KEY=%s\n' \"${FLASK_SECRET_KEY}\"; \
     [ -n \"${BIRDLENSE_ENV:-}\" ] && printf 'BIRDLENSE_ENV=%s\n' \"${BIRDLENSE_ENV}\"; \
     printf 'PROCESSOR_SECRET=%s\n' \"${PROCESSOR_SECRET}\") > ${REMOTE_DIR}/app/.env.new && \
    mv ${REMOTE_DIR}/app/.env.new ${REMOTE_DIR}/app/.env"
fi

# 1.6 Идемпотентные значения в app/.env для production (только если строки ещё не заданы).
# TRUSTED_PROXY=1 — rate limit и логика IP за nginx; CLEANUP — убрать legacy-плейсхолдеры импорта при старте.
if [ "${BIRDLENSE_ENV:-}" = "production" ] && [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  echo "1.6 Production .env defaults (append if missing)..."
  ssh ${SSH_OPTS} "${HOST}" "F=\"${REMOTE_DIR}/app/.env\"; touch \"\$F\"; \
    grep -qE '^TRUSTED_PROXY=' \"\$F\" || echo 'TRUSTED_PROXY=1' >> \"\$F\"; \
    grep -qE '^BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=' \"\$F\" || echo 'BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=1' >> \"\$F\""
fi

# 1.8 Intel GPU: на сервере с /dev/dri/renderD128 — создать/обновить override (devices + sysfs для метрик GPU)
echo "1.8 Проверка Intel GPU на сервере..."
ssh ${SSH_OPTS} "${HOST}" "cd ${REMOTE_DIR}/app && \
  if [ -e /dev/dri/renderD128 ]; then \
    cp docker-compose.intel.example.yml docker-compose.override.yml && echo '  override установлен (Intel GPU + sysfs)'; \
  else \
    rm -f docker-compose.override.yml; \
  fi"

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
health_ok=0
for htry in $(seq 1 5); do
  if curl -sS -L --max-time 20 -f "${DEPLOY_URL}/api/ui/health" >/dev/null 2>&1; then
    health_ok=1
    break
  fi
  [[ $htry -lt 5 ]] && sleep 5
done
[[ $health_ok -eq 1 ]] && echo "    OK" || echo "    FAIL (проверьте ${DEPLOY_URL}; с хоста: curl -sS -L ${DEPLOY_URL}/api/ui/health)"
echo "  - API cameras:"
cameras=$(curl -sS -L --max-time 20 -f "${DEPLOY_URL}/api/ui/cameras" 2>/dev/null | head -c 150) && echo "    ${cameras}..." || echo "    (не доступен)"
echo ""
echo "=== Готово. UI: ${DEPLOY_URL} ==="
echo "Настройки и записи на сервере не тронуты."
echo ""
echo "Если API недоступен из браузера: добавьте на сервере в app/.env:"
echo "  CORS_ORIGINS=${DEPLOY_URL}"
