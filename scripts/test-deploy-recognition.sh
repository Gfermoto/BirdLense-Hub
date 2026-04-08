#!/bin/bash
# Тест распознавания после деплоя: запускает процессор на существующей записи.
# Провоцирует событие — при обнаружении птицы создаёт новую запись в UI.
#
# Запуск: ./scripts/test-deploy-recognition.sh
#         VIDEO_ID=37 ./scripts/test-deploy-recognition.sh   # тест на видео 37
# Требует: deploy.local.sh (HOST, REMOTE_DIR, DEPLOY_URL) или переменные окружения

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
DATA_DIR="${REMOTE_DIR}/app/data"
RECORDINGS="${DATA_DIR}/recordings"
API_URL="${DEPLOY_URL:-http://localhost:8085}"

# Как в scripts/deploy.sh: нестандартный SSH-порт (VPS)
_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"

echo "=== Тест распознавания на ${HOST} ==="

if [ -n "${VIDEO_ID}" ]; then
  # Получить путь видео по ID через API
  VIDEO_PATH=$(ssh ${SSH_OPTS} "${HOST}" "curl -s '${API_URL}/api/ui/videos/${VIDEO_ID}'" | jq -r '.video_path // empty')
  if [ -z "$VIDEO_PATH" ]; then
    echo "Ошибка: видео ${VIDEO_ID} не найдено (API: ${API_URL}/api/ui/videos/${VIDEO_ID})"
    exit 1
  fi
  # data/recordings/YYYY/MM/DD/HHMMSS/video.mp4 -> /app/data/recordings/...
  CONTAINER_VIDEO="/app/${VIDEO_PATH}"
  echo "Видео ID ${VIDEO_ID}: ${VIDEO_PATH}"
else
  # Найти последнюю запись video.mp4 (по времени модификации)
  VIDEO=$(ssh ${SSH_OPTS} "${HOST}" "find ${RECORDINGS} -name 'video.mp4' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2")
  if [ -z "$VIDEO" ]; then
    echo "Ошибка: записей не найдено в ${RECORDINGS}"
    echo "Добавьте хотя бы одну запись с птицей или укажите VIDEO_ID=37"
    exit 1
  fi
  CONTAINER_VIDEO="/app/data/recordings/${VIDEO#*recordings/}"
  echo "Видео: ${VIDEO}"
fi

echo "В контейнере: ${CONTAINER_VIDEO}"
echo ""
echo "Запуск процессора (--fake-motion true, MQTT_CLIENT_ID=birdlense_aggregator_test)..."
echo "При обнаружении птицы появится новая запись в UI."
echo ""

ssh ${SSH_OPTS} "${HOST}" "docker exec -e PYTHONPATH=/app -e MQTT_CLIENT_ID=birdlense_aggregator_test birdlense python /app/processor/src/main.py '${CONTAINER_VIDEO}' --fake-motion true"

echo ""
echo "Готово. Проверьте UI на новую запись."
