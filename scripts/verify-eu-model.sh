#!/bin/bash
# Проверка EU-модели (YOLO 11, birds-525 + iNaturalist) на сервере.
# Классификатор: classification/weights/best.pt (HF gfermoto/birdlense-birds-eu).
# Бинарник по умолчанию: detection/weights/yolo11n.pt (COCO, в рантайме только cls 14 bird).
#
# Запуск: ./scripts/verify-eu-model.sh
# Требует: deploy.local.sh с DEPLOY_HOST и DEPLOY_REMOTE_DIR

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:?Set DEPLOY_HOST in deploy.local.sh}"
# Как в scripts/deploy.sh по умолчанию; /opt/birdlense — устаревший пример из старых инструкций
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"

_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"

echo "=== Проверка EU-модели на ${HOST} ==="
echo ""

echo "1. Файлы весов (classification best.pt + binary detection):"
ssh ${SSH_OPTS} "${HOST}" "ls -la ${REMOTE_DIR}/app/processor/models/classification/weights/best*.pt ${REMOTE_DIR}/app/processor/models/detection/weights/yolo11n.pt 2>/dev/null || true"
echo ""

echo "1b. CUDA в контейнере (если пусто — только CPU):"
ssh ${SSH_OPTS} "${HOST}" "docker exec birdlense python3 -c \"
import torch
print('   cuda_available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('   device:', torch.cuda.get_device_name(0))
\" 2>/dev/null || echo '   (torch check failed)'"
echo ""

echo "2. Классы EU-классификатора best.pt (должно быть ~491):"
ssh ${SSH_OPTS} "${HOST}" "docker exec birdlense python3 -c \"
from ultralytics import YOLO
m = YOLO('/app/processor/models/classification/weights/best.pt', task='classify')
n = len(m.names)
print(f'   Классов: {n}')
eu = ['Parus major', 'Fringilla coelebs', 'Erithacus rubecula', 'Cyanistes caeruleus', 'Carduelis carduelis']
found = [name for name in m.names.values() if any(e in name for e in eu)]
print(f'   EU-виды (примеры): {found[:5]}')
\""
echo ""

echo "2b. Бинарный детектор (дефолт: COCO yolo11n, 80 классов; в конфиге allowlist только bird=14):"
ssh ${SSH_OPTS} "${HOST}" "docker exec birdlense python3 -c \"
from ultralytics import YOLO
m = YOLO('/app/processor/models/detection/weights/yolo11n.pt', task='detect')
print('   Классов:', len(m.names))
print('   cls14=', m.names.get(14))
print('   names sample:', dict(list(m.names.items())[:4]), '...')
\" 2>/dev/null || echo '   ОШИБКА: не удалось загрузить yolo11n.pt'"
echo ""

echo "3. Тест классификатора (случайный кадр):"
ssh ${SSH_OPTS} "${HOST}" "docker exec birdlense python3 -c \"
import numpy as np
from ultralytics import YOLO
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
ssh ${SSH_OPTS} "${HOST}" "grep -E 'detection_strategy|classifier:' ${REMOTE_DIR}/app/app_config/default_config.yaml 2>/dev/null || grep -E 'detection_strategy|classifier:' ${REMOTE_DIR}/app/app_config/user_config.yaml 2>/dev/null || echo '   (default_config)'"
echo ""

echo "=== Итог ==="
ssh ${SSH_OPTS} "${HOST}" "docker exec birdlense python3 -c \"
from ultralytics import YOLO
c = YOLO('/app/processor/models/classification/weights/best.pt', task='classify')
n = len(c.names)
print('   classifier_classes:', n)
if n < 50:
    print('   WARNING: ожидались сотни классов (EU ~491). Сейчас мало классов — виды будут «ломаться».')
d = YOLO('/app/processor/models/detection/weights/yolo11n.pt', task='detect')
print('   binary_classes:', len(d.names))
\" 2>/dev/null || true"
echo "EU-модель в норме: classifier_classes ~491, в списке EU-виды, cuda_available=True (если есть GPU)."
