#!/usr/bin/env bash
# BirdLense Hub — начальная настройка Orin NX / NANO
# Использование: bash scripts/setup-orin.sh [--defaults]
#
# Делает:
#   1. Проверяет окружение (NVIDIA runtime, JetPack, CUDA)
#   2. Создаёт app/.env с BIRDLENSE_STRICT_API_AUTH=0
#   3. Копирует user_config.orin.example.yaml → user_config.yaml (если ещё нет)
#   4. Собирает образ и запускает стек
#   5. Проверяет health
#
# После запуска — UI на http://<orin-ip>:8085

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "=== BirdLense Hub — Orin Setup ==="
echo ""

# 1. Проверка NVIDIA
echo "1. Проверка окружения..."
if ! nvidia-smi &>/dev/null; then
    echo "ОШИБКА: nvidia-smi не работает. Установите NVIDIA JetPack / CUDA."
    exit 1
fi
NVIDIA_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)
echo "  NVIDIA driver: ${NVIDIA_VERSION:-unknown}"
echo ""

# 2. Проверка Docker + NVIDIA Container Toolkit
echo "2. Проверка Docker..."
if ! docker info &>/dev/null; then
    echo "ОШИБКА: Docker недоступен. Установите Docker + nvidia-container-toolkit."
    echo "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    exit 1
fi
if ! docker info 2>/dev/null | grep -qi 'nvidia'; then
    echo "ПРЕДУПРЕЖДЕНИЕ: nvidia-container-runtime не обнаружен — GPU в контейнере не будет работать."
    echo "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
fi
echo "  Docker: OK"
echo ""

# 3. Docker Compose check
echo "3. Проверка Docker Compose..."
COMPOSE_CMD=""
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "ОШИБКА: docker compose не найден."
    exit 1
fi
echo "  Compose: ${COMPOSE_CMD}"
echo ""

# 4. .env
echo "4. Настройка .env..."
ENV_FILE="${REPO_ROOT}/app/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    cp "${REPO_ROOT}/app/.env.example" "${ENV_FILE}" 2>/dev/null || touch "${ENV_FILE}"
    echo "  Создан ${ENV_FILE}"
fi

# STRICT_API_AUTH=0 для первого запуска
if grep -qE '^BIRDLENSE_STRICT_API_AUTH=' "${ENV_FILE}"; then
    sed -i 's/^BIRDLENSE_STRICT_API_AUTH=.*/BIRDLENSE_STRICT_API_AUTH=0/' "${ENV_FILE}"
else
    echo 'BIRDLENSE_STRICT_API_AUTH=0' >> "${ENV_FILE}"
fi

# FLASK_SECRET_KEY если нет
if ! grep -qE '^FLASK_SECRET_KEY=' "${ENV_FILE}"; then
    echo "FLASK_SECRET_KEY=$(openssl rand -hex 32)" >> "${ENV_FILE}"
fi

# PROCESSOR_SECRET если нет
if ! grep -qE '^PROCESSOR_SECRET=' "${ENV_FILE}"; then
    echo "PROCESSOR_SECRET=$(openssl rand -hex 16)" >> "${ENV_FILE}"
fi

# BIRDLENSE_ENV если нет
if ! grep -qE '^BIRDLENSE_ENV=' "${ENV_FILE}"; then
    echo "BIRDLENSE_ENV=production" >> "${ENV_FILE}"
fi

echo "  .env: OK (BIRDLENSE_STRICT_API_AUTH=0)"
echo ""

# 5. user_config.yaml
echo "5. Настройка конфига..."
USER_CONFIG="${REPO_ROOT}/app/app_config/user_config.yaml"
if [[ ! -f "${USER_CONFIG}" ]]; then
    if [[ -f "${REPO_ROOT}/app/app_config/user_config.orin.example.yaml" ]]; then
        cp "${REPO_ROOT}/app/app_config/user_config.orin.example.yaml" "${USER_CONFIG}"
        echo "  Создан ${USER_CONFIG} (из user_config.orin.example.yaml)"
    elif [[ -f "${REPO_ROOT}/app/app_config/default_config.yaml" ]]; then
        cp "${REPO_ROOT}/app/app_config/default_config.yaml" "${USER_CONFIG}"
        echo "  Создан ${USER_CONFIG} (из default_config.yaml)"
    fi
    echo "  ВАЖНО: отредактируйте ${USER_CONFIG} — укажите камеры, пароли и т.д."
else
    echo "  ${USER_CONFIG} уже существует — не трогаем."
fi
echo ""

# 5b. Processor models (Orin)
echo "5b. Processor models..."
if bash "${REPO_ROOT}/scripts/fetch-processor-models-orin.sh"; then
  echo "  models: OK"
else
  echo "  models: не все артефакты — см. scripts/fetch-processor-models-orin.sh"
fi
echo ""

# 6. Сборка образа
echo "6. Сборка Docker образа (Orin, CUDA 13, onnxruntime-gpu)..."
echo "  Время сборки: 5-15 мин (зависит от Orin)."
echo ""
cd "${REPO_ROOT}/app"
BIRDLENSE_PLATFORM=orin ${COMPOSE_CMD} build --no-cache birdlense
echo ""

# 7. Запуск
echo "7. Запуск стека..."
BIRDLENSE_PLATFORM=orin ${COMPOSE_CMD} up -d
echo ""

# 8. Ждём health
echo "8. Ожидание health (до 3 мин)..."
ATTEMPTS=36
SLEEP=5
HEALTH_URL="http://127.0.0.1:${BIRDLENSE_PORT:-8085}"
for i in $(seq 1 ${ATTEMPTS}); do
    if curl -sf "${HEALTH_URL}/api/ui/health" > /dev/null 2>&1; then
        echo "  Health: OK (через $((i * SLEEP)) сек)"
        break
    fi
    if [[ "${i}" -eq "${ATTEMPTS}" ]]; then
        echo "  Health: не дождались. Проверьте: docker logs birdlense --tail=50"
        echo "  UI может быть на http://<IP_ORINA>:${BIRDLENSE_PORT:-8085}"
        exit 1
    fi
    sleep ${SLEEP}
done
echo ""

# 9. Итог
echo "=== Готово ==="
echo "  UI: ${HEALTH_URL}"
echo "  MCP: ${HEALTH_URL}/mcp"
echo ""
echo "  Первый вход: без пароля (BIRDLENSE_STRICT_API_AUTH=0)"
echo "  Настройки: System → Settings в UI, или отредактируйте ${USER_CONFIG}"
echo "  Камеры: добавьте в UI через System → Sources → Add Camera"
echo ""
echo "  Если UI не открывается — проверьте:"
echo "    docker logs birdlense --tail=50"
echo "    docker ps -a --filter name=birdlense"
echo ""
echo "  Ручная смена порта: BIRDLENSE_PORT=9090 bash scripts/setup-orin.sh"
