#!/bin/bash
# Проверка EU-модели (YOLO 11, birds-525 + iNaturalist) на сервере.
# Убеждаемся, что best.pt — европейские птицы и веса работают.
#
# Запуск: ./scripts/verify-eu-model.sh
# Требует: deploy.local.sh с DEPLOY_HOST и DEPLOY_REMOTE_DIR

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:?Set DEPLOY_HOST in deploy.local.sh}"
# Как в scripts/deploy.sh по умолчанию; /opt/birdlense — устаревший пример из старых инструкций
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"

echo "=== Проверка EU-модели на ${HOST} ==="
echo ""

echo "1. Файлы весов:"
ssh "${HOST}" "ls -la ${REMOTE_DIR}/app/processor/models/classification/weights/best*.pt 2>/dev/null || true"
echo ""

echo "2. Классы модели best.pt (должно быть ~491):"
ssh "${HOST}" "docker exec birdlense python3 -c \"
from ultralytics import YOLO
m = YOLO('/app/processor/models/classification/weights/best.pt', task='classify')
n = len(m.names)
print(f'   Классов: {n}')
eu = ['Parus major', 'Fringilla coelebs', 'Erithacus rubecula', 'Cyanistes caeruleus', 'Carduelis carduelis']
found = [name for name in m.names.values() if any(e in name for e in eu)]
print(f'   EU-виды (примеры): {found[:5]}')
\""
echo ""

echo "3. Тест классификатора (случайный кадр):"
ssh "${HOST}" "docker exec birdlense python3 -c \"
from ultralytics import YOLO
import numpy as np
m = YOLO('/app/processor/models/classification/weights/best.pt', task='classify')
crop = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
r = m(crop, verbose=False)
if r and r[0].probs:
    name = r[0].names[r[0].probs.top1]
    conf = r[0].probs.top1conf.item()
    print(f'   OK: {name} ({conf:.1%})')
else:
    print('   ОШИБКА: классификатор не ответил')
\""
echo ""

echo "4. Конфиг (detection_strategy, classifier path):"
ssh "${HOST}" "grep -E 'detection_strategy|classifier:' ${REMOTE_DIR}/app/app_config/default_config.yaml 2>/dev/null || grep -E 'detection_strategy|classifier:' ${REMOTE_DIR}/app/app_config/user_config.yaml 2>/dev/null || echo '   (default_config)'"
echo ""

echo "=== Готово. EU-модель активна, если: классов ~491, EU-виды в списке, тест OK. ==="
