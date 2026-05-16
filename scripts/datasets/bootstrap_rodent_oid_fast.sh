#!/usr/bin/env bash
# Быстрый добор binary/rodent из Open Images V6 только split validation (меньше CSV/каналов, чем full train).
# Домен — дневной RGB; для IR/ночных камер см. README в комментарии ниже или make dataset-import-roboflow-rodent.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DET_ROOT="${DETECTOR_ETL_ROOT:-$REPO_ROOT/datasets/new/detector}"
PYTHON="${BIRDLENSE_PYTHON:-$REPO_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then PYTHON="python3"; fi

RT="${RODENT_OID_TRAIN:-2000}"
RV="${RODENT_OID_VAL:-550}"
CH="${RODENT_CHUNK:-120}"
RCS="${RODENT_CLASSES:-Squirrel,Mouse,Hamster,Rabbit,Porcupine}"

echo ">>> rodent OID fast: root=$DET_ROOT train=$RT val=$RV chunk=$CH classes=$RCS"
"$PYTHON" "$SCRIPT_DIR/bootstrap_detector_yolo.py" \
  --root "$DET_ROOT" \
  --skip-birds \
  --skip-background \
  --rodent-validation-only \
  --rodent-train "$RT" \
  --rodent-val "$RV" \
  --rodent-classes "$RCS" \
  --chunk-size "$CH"
