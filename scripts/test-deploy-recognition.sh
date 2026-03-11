#!/bin/bash
# Тест распознавания после деплоя: запускает процессор на существующей записи.
# Провоцирует событие — при обнаружении птицы создаёт новую запись в UI.
#
# Запуск: ./scripts/test-deploy-recognition.sh
# Требует: deploy.local.sh (HOST, REMOTE_DIR) или переменные окружения

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
DATA_DIR="${REMOTE_DIR}/app/data"
RECORDINGS="${DATA_DIR}/recordings"

echo "=== Тест распознавания на ${HOST} ==="

# Найти последнюю запись video.mp4 (по времени модификации)
VIDEO=$(ssh "${HOST}" "find ${RECORDINGS} -name 'video.mp4' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2")

if [ -z "$VIDEO" ]; then
  echo "Ошибка: записей не найдено в ${RECORDINGS}"
  echo "Добавьте хотя бы одну запись с птицей перед тестом."
  exit 1
fi

# Путь в контейнере (data монтируется как /app/data)
CONTAINER_VIDEO="/app/data/recordings/${VIDEO#*recordings/}"

echo "Видео: ${VIDEO}"
echo "В контейнере: ${CONTAINER_VIDEO}"
echo ""
echo "Запуск процессора (--fake-motion true)..."
echo "При обнаружении птицы появится новая запись в UI."
echo ""

ssh "${HOST}" "docker exec birdlense python /app/processor/src/main.py '${CONTAINER_VIDEO}' --fake-motion true"

echo ""
echo "Готово. Проверьте UI на новую запись."
