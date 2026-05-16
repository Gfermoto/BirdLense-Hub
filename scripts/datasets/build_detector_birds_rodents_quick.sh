#!/usr/bin/env bash
# Быстрый путь к датасету детекции: птицы (COCO + OID) + грызуны (OID через волны), без фона D/E.
#
#   bash scripts/datasets/build_detector_birds_rodents_quick.sh
#
# Переменные (опционально):
#   DETECTOR_ETL_ROOT — корень датасета (по умолчанию repo/datasets/new/detector)
#   DETECTOR_PHASE_END=3 — только A+B+C (дефолт)
#   PYTHON, WAVE_PAUSE, CHUNK_SIZE, BG_SCAN_CHUNK — как у build_detector_dataset_waves.sh
#
# Доп. грызуны из COCO (LILA после скачивания JSON + images):
#   export LILA_COCO_JSON=/path/to/instances.json
#   export LILA_IMAGES_DIR=/path/to/image/root
#   export LILA_SPLIT=train          # train | val
#   export LILA_ROD_MAX=4000
#   bash scripts/datasets/build_detector_birds_rodents_quick.sh
#
# Обогащение вручную после волн: make dataset-import-cub CUB_ROOT=…  /  dataset-import-roboflow-bird-feeder
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DETECTOR_ETL_ROOT="${DETECTOR_ETL_ROOT:-$REPO_ROOT/datasets/new/detector}"
export DETECTOR_ETL_ROOT
export DETECTOR_PHASE_END="${DETECTOR_PHASE_END:-3}"

if [[ -z "${PYTHON:-}" && -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif [[ -z "${PYTHON:-}" ]]; then
  PYTHON="python3"
fi

mkdir -p "$REPO_ROOT/datasets/logs"

echo ">>> Waves A+B+C (birds COCO + OID + rodent OID), без фона. ROOT=$DETECTOR_ETL_ROOT PHASE_END=$DETECTOR_PHASE_END"
bash "$SCRIPT_DIR/build_detector_dataset_waves.sh"

if [[ -n "${LILA_COCO_JSON:-}" && -d "${LILA_IMAGES_DIR:-}" ]]; then
  echo ">>> LILA/COCO → binary/rodent/${LILA_SPLIT:-train}"
  "$PYTHON" "$SCRIPT_DIR/import_coco_rodents_to_binary.py" \
    --root "$DETECTOR_ETL_ROOT" \
    --coco-json "$LILA_COCO_JSON" \
    --images-dir "$LILA_IMAGES_DIR" \
    --split "${LILA_SPLIT:-train}" \
    --max-images "${LILA_ROD_MAX:-5000}" \
    --seed "${LILA_SEED:-42}" \
    --prefix "${LILA_PREFIX:-lila_}"
fi

echo ">>> dataset-merge-three-class"
make -C "$REPO_ROOT" dataset-merge-three-class

if [[ "${SKIP_VERIFY:-0}" == "1" ]]; then
  echo ">>> verify пропущен (SKIP_VERIFY=1)"
else
  echo ">>> detector-etl-verify-birds-rodents"
  make -C "$REPO_ROOT" detector-etl-verify-birds-rodents
fi

echo "Done. merged YOLO dataset: $DETECTOR_ETL_ROOT/yolo (dataset.yaml)"
