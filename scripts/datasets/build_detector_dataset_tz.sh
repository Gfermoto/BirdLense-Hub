#!/usr/bin/env bash
# Один вход под ТЗ детектора Bird / Rodent / Background:
#   волны bootstrap A–E → гейт binary verify → merge → dedupe yolo → проверка разметки train/val.
#
#   bash scripts/datasets/build_detector_dataset_tz.sh
#
# Env:
#   DETECTOR_ETL_ROOT     — корень (default: repo/datasets/new/detector)
#   DETECTOR_PHASE_BEGIN/END — см. build_detector_dataset_waves.sh (default 1→5)
#   SKIP_WAVES=1          — пропустить волны (уже заполненный binary/)
#   SKIP_VERIFY=1         — не вызывать detector-etl-verify-birds-rodents
#   SKIP_LILA=1           — не импортировать LILA даже если заданы переменные ниже
#   LILA_COCO_JSON / LILA_IMAGES_DIR — опционально import_coco_rodents_to_binary
#   BIRDLENSE_BOOTSTRAP_ZOO_RETRIES — слабая сеть
#   BIRDLENSE_BOOTSTRAP_CHUNK_MAX + BIRDLENSE_BOOTSTRAP_KEEP_CHUNK_MAX=1 — явный cap порций
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export DETECTOR_ETL_ROOT="${DETECTOR_ETL_ROOT:-$REPO_ROOT/datasets/new/detector}"

export BIRDLENSE_BOOTSTRAP_ZOO_RETRIES="${BIRDLENSE_BOOTSTRAP_ZOO_RETRIES:-25}"
# Сброс CHUNK_MAX из родительской оболочки (Cursor/терминал), иначе COCO залипает на cap=96.
if [[ "${BIRDLENSE_BOOTSTRAP_KEEP_CHUNK_MAX:-0}" != "1" ]]; then
  unset BIRDLENSE_BOOTSTRAP_CHUNK_MAX
fi

if [[ -z "${PYTHON:-}" && -x "$REPO_ROOT/.venv/bin/python" ]]; then
  export PYTHON="$REPO_ROOT/.venv/bin/python"
elif [[ -z "${PYTHON:-}" ]]; then
  export PYTHON="python3"
fi

mkdir -p "$REPO_ROOT/datasets/logs"
LOG="$REPO_ROOT/datasets/logs/build_detector_tz_$(date -u +%Y%m%dT%H%M%SZ).log"
exec >> >(tee -a "$LOG") 2>&1

echo "===== TZ dataset build $(date -Is) ROOT=$DETECTOR_ETL_ROOT log=$LOG ====="

if [[ "${SKIP_WAVES:-0}" != "1" ]]; then
  export DETECTOR_PHASE_END="${DETECTOR_PHASE_END:-5}"
  export DETECTOR_PHASE_BEGIN="${DETECTOR_PHASE_BEGIN:-1}"
  bash "$SCRIPT_DIR/build_detector_dataset_waves.sh"
else
  echo ">>> SKIP_WAVES=1 — двоичный слой не трогаем"
fi

if [[ "${SKIP_LILA:-0}" != "1" && -n "${LILA_COCO_JSON:-}" && -d "${LILA_IMAGES_DIR:-}" ]]; then
  echo ">>> LILA/COCO rodents → binary/rodent/${LILA_SPLIT:-train}"
  "$PYTHON" "$SCRIPT_DIR/import_coco_rodents_to_binary.py" \
    --root "$DETECTOR_ETL_ROOT" \
    --coco-json "$LILA_COCO_JSON" \
    --images-dir "$LILA_IMAGES_DIR" \
    --split "${LILA_SPLIT:-train}" \
    --max-images "${LILA_ROD_MAX:-5000}" \
    --seed "${LILA_SEED:-42}" \
    --prefix "${LILA_PREFIX:-lila_}"
fi

if [[ "${SKIP_VERIFY:-0}" != "1" ]]; then
  echo ">>> detector-etl-verify-birds-rodents"
  make -C "$REPO_ROOT" detector-etl-verify-birds-rodents
else
  echo ">>> SKIP_VERIFY=1"
fi

echo ">>> dataset-merge-three-class"
make -C "$REPO_ROOT" dataset-merge-three-class

echo ">>> dataset-dedupe-detector-yolo"
make -C "$REPO_ROOT" dataset-dedupe-detector-yolo

YOLO_ROOT="$DETECTOR_ETL_ROOT/yolo"
for split in train val; do
  ld="$YOLO_ROOT/$split/labels"
  echo ">>> validate YOLO labels $ld"
  LABELS_DIR="$ld" CLASS_COUNT=3 make -C "$REPO_ROOT" dataset-validate-yolo-labels
done

echo "===== TZ OK: $YOLO_ROOT/dataset.yaml ====="
