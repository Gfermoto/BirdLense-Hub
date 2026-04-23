#!/bin/bash
# Деплой BirdLense Hub
# Локальные настройки (IP, URL) — в scripts/deploy.local.sh (не коммитить)
# Критично: app/data целиком не синхронизируем (как в .github/workflows/deploy.yml) — записи, БД, dataset и images остаются на сервере. Корневой datasets/ (YOLO) не синхронизируем. user_config не перезаписываем.
# Сам следит и исправляет: rsync на сервере, повтор при сбоях

set -euo pipefail

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
command -v node >/dev/null 2>&1 || { echo "Ошибка: node не найден. Нужен Node.js 20.18+ или 22.x для локальной сборки UI (см. app/ui/package.json engines)."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Ошибка: npm не найден. Нужен npm 10+ для локальной сборки UI."; exit 1; }
(cd app/ui && npm ci --no-audit --no-fund && npm run build) || { echo "Ошибка: npm ci / npm run build не удались"; exit 1; }

# 0.95 Бэкап user_config на сервере перед rsync (восстановление: scripts/restore-config.sh или .bak.deploy-*)
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  echo "0.95 Бэкап user_config.yaml на сервере (если есть)..."
  ssh ${SSH_OPTS} "${HOST}" "UC='${REMOTE_DIR}/app/app_config/user_config.yaml'; \
    if [ -f \"\$UC\" ]; then cp \"\$UC\" \"\${UC}.bak.deploy-\$(date +%Y%m%d%H%M%S)\"; echo '  OK: снимок .bak.deploy-*'; fi" || true
fi

# 1. Синхронизация кода (rsync устойчивее к обрывам, повтор при сбое)
echo "1. Синхронизация кода..."
RSYNC_EXCLUDES="--exclude=.git --exclude=node_modules --exclude=__pycache__ --exclude=.env"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=datasets --exclude=app/data --exclude=app/.env"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/app_config/user_config.yaml --exclude=scripts/deploy.local.sh"
# Локальные venv / сборка док — не на сервер
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.venv-docs-tmp --exclude=.venv-docs --exclude=.venv-ci --exclude=site"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/.venv --exclude=.venv-datasets"
# Кэши линтера/тестов (часто root после docker compose run) — иначе rsync code 23 Permission denied
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/.ruff_cache --exclude=app/.pytest_cache"
# CodeQL CLI, БД и SARIF (scripts/codeql-local.sh) — десятки МБ/ГБ, на хаб не нужны
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.tools"
# Не удалять на сервере: веса .pt; user_config (exclude + P — двойная страховка от --delete).
RSYNC_FILTER_PROTECT=(--filter "P app/processor/models/detection/weights/*.pt" --filter "P app/processor/models/classification/weights/*.pt" --filter "P app/app_config/user_config.yaml")
sync_ok=0
for attempt in $(seq 1 ${SYNC_RETRIES}); do
  if [[ "${HOST}" == "localhost" || "${HOST}" == "127.0.0.1" ]]; then
    rsync -a --delete ${RSYNC_EXCLUDES} "${RSYNC_FILTER_PROTECT[@]}" ./ "${REMOTE_DIR}/" && sync_ok=1 && break
  else
    rsync -avz --delete -e "ssh ${SSH_OPTS}" ${RSYNC_EXCLUDES} "${RSYNC_FILTER_PROTECT[@]}" ./ "${HOST}:${REMOTE_DIR}/" && sync_ok=1 && break
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
if [ -n "${MCP_TOKEN:-}" ] || [ -n "${PROCESSOR_SECRET:-}" ] || [ -n "${FLASK_SECRET_KEY:-}" ] || [ -n "${BIRDLENSE_ENV:-}" ] || [ -n "${BIRDLENSE_STRICT_API_AUTH:-}" ] || [ -n "${BIRDLENSE_UI_API_KEY:-}" ]; then
  echo "1.5 Запись секретов в app/.env на сервере (точечная подмена ключей; остальные строки .env сохраняются)..."
  # shellcheck disable=SC2090
  ssh ${SSH_OPTS} "${HOST}" \
    env \
    "REMOTE_DIR=${REMOTE_DIR}" \
    "MCP_TOKEN=${MCP_TOKEN:-}" \
    "PROCESSOR_SECRET=${PROCESSOR_SECRET}" \
    "FLASK_SECRET_KEY=${FLASK_SECRET_KEY:-}" \
    "BIRDLENSE_ENV=${BIRDLENSE_ENV:-}" \
    "BIRDLENSE_STRICT_API_AUTH=${BIRDLENSE_STRICT_API_AUTH:-}" \
    "BIRDLENSE_UI_API_KEY=${BIRDLENSE_UI_API_KEY:-}" \
    bash -s <<'ENDSSH_MERGE_ENV'
set -euo pipefail
F="${REMOTE_DIR}/app/.env"
mkdir -p "${REMOTE_DIR}/app"
SIZE=$(stat -c%s "$F" 2>/dev/null || echo 0)
if [ ! -f "$F" ] || [ "$SIZE" -gt 1048576 ]; then
  cp "${REMOTE_DIR}/app/.env.example" "$F" 2>/dev/null || touch "$F"
fi
# Удаляем из .env только те ключи, которые сейчас задаём с непустым значением (остальное на сервере не трогаем).
_merge_env_kv() {
  local key="$1" val="$2"
  if [ -z "$val" ] || [ ! -f "$F" ]; then
    return 0
  fi
  grep -v -E "^${key}=" "$F" >"${F}.new" || true
  mv "${F}.new" "$F"
  printf '%s=%s\n' "$key" "$val" >>"$F"
}
_merge_env_kv MCP_TOKEN "${MCP_TOKEN:-}"
_merge_env_kv FLASK_SECRET_KEY "${FLASK_SECRET_KEY:-}"
_merge_env_kv BIRDLENSE_ENV "${BIRDLENSE_ENV:-}"
_merge_env_kv BIRDLENSE_STRICT_API_AUTH "${BIRDLENSE_STRICT_API_AUTH:-}"
_merge_env_kv BIRDLENSE_UI_API_KEY "${BIRDLENSE_UI_API_KEY:-}"
if [ -f "$F" ]; then
  grep -v -E '^PROCESSOR_SECRET=' "$F" >"${F}.new" || true
  mv "${F}.new" "$F"
fi
printf 'PROCESSOR_SECRET=%s\n' "${PROCESSOR_SECRET}" >>"$F"
ENDSSH_MERGE_ENV
fi

# 1.6 Идемпотентные значения в app/.env для production (только если строки ещё не заданы).
# TRUSTED_PROXY=1 — rate limit и логика IP за nginx; CLEANUP — убрать legacy-плейсхолдеры импорта при старте.
if [ "${BIRDLENSE_ENV:-}" = "production" ] && [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  echo "1.6 Production .env defaults (append if missing)..."
  ssh ${SSH_OPTS} "${HOST}" "F=\"${REMOTE_DIR}/app/.env\"; touch \"\$F\"; \
    grep -qE '^TRUSTED_PROXY=' \"\$F\" || echo 'TRUSTED_PROXY=1' >> \"\$F\"; \
    grep -qE '^BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=' \"\$F\" || echo 'BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=1' >> \"\$F\""
fi

# 1.8 Intel GPU: при наличии renderD* — сгенерировать override (card+render, group_add video/render хоста, sysfs, PERFMON)
# 1.8b PMU / intel_gpu_top: дефолт 3 (и иногда даже 1) режет perf в контейнере при CAP_PERFMON → «Failed to initialize PMU». Значение 0 проверено на VPS; −1 только при необходимости.
echo "1.8 Проверка Intel GPU на сервере..."
ssh ${SSH_OPTS} "${HOST}" "set -e; cd '${REMOTE_DIR}/app' && bash scripts/docker-compose-intel-override-gen.sh; \
  if [ -f docker-compose.override.yml ]; then \
    echo '1.8b sysctl kernel.perf_event_paranoid=0 → /etc/sysctl.d/99-birdlense-perf.conf'; \
    printf '%s\n' 'kernel.perf_event_paranoid=0' > /etc/sysctl.d/99-birdlense-perf.conf; \
    sysctl -p /etc/sysctl.d/99-birdlense-perf.conf || true; \
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
echo "  - Shared verify contract:"
BASE_URL="${DEPLOY_URL}" ATTEMPTS=20 SLEEP_SEC=3 CHECK_CAMERAS=1 ./scripts/verify-stack.sh
echo ""
echo "=== Готово. UI: ${DEPLOY_URL} ==="
echo "Записи и БД не трогаем; user_config.yaml не синхронизируем (есть бэкап .bak.deploy-* перед rsync)."
echo ""
echo "Если API недоступен из браузера: добавьте на сервере в app/.env:"
echo "  CORS_ORIGINS=${DEPLOY_URL}"
