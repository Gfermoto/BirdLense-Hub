#!/usr/bin/env bash
# Перезапуск волнового сбора детектора (фазы D+E по умолчанию). Из корня репо:
#   bash scripts/datasets/restart_detector_dataset_waves.sh
#
# Переопределения (env):
#   DETECTOR_PHASE_BEGIN RUN_MERGE SKIP_KILL BIRDLENSE_BOOTSTRAP_BG_PROGRESS_EVERY …
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

LOG="$REPO_ROOT/datasets/logs/detector_waves.log"
mkdir -p "$(dirname "$LOG")"
DONE="$REPO_ROOT/datasets/logs/.detector_etl_done"
rm -f "$DONE"

if [[ "${SKIP_KILL:-}" != "1" ]]; then
  pkill -TERM -f 'bootstrap_detector_yolo\.py' 2>/dev/null || true
  sleep 2
  pkill -KILL -f 'bootstrap_detector_yolo\.py' 2>/dev/null || true
  pkill -TERM -f 'scripts/datasets/build_detector_dataset_waves\.sh' 2>/dev/null || true
  sleep 1
  pkill -KILL -f 'scripts/datasets/build_detector_dataset_waves\.sh' 2>/dev/null || true
fi

PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

printf '\n===== restart %s D+E restart_detector_dataset_waves.sh =====\n' "$(date -Is)" >>"$LOG"

nohup env PYTHONUNBUFFERED=1 \
  DETECTOR_PHASE_BEGIN="${DETECTOR_PHASE_BEGIN:-4}" \
  BG_SCAN_CHUNK="${BG_SCAN_CHUNK:-1200}" \
  DETECTOR_BG_TRAIN_POOL="${DETECTOR_BG_TRAIN_POOL:-40000}" \
  DETECTOR_BG_VAL_POOL="${DETECTOR_BG_VAL_POOL:-32000}" \
  BIRDLENSE_BOOTSTRAP_BG_PROGRESS_EVERY="${BIRDLENSE_BOOTSTRAP_BG_PROGRESS_EVERY:-50}" \
  PYTHON="$PYTHON" \
  RUN_MERGE="${RUN_MERGE:-1}" \
  bash "$REPO_ROOT/scripts/datasets/build_detector_dataset_waves.sh" >>"$LOG" 2>&1 &
W_PID=$!

echo "$W_PID" >"$REPO_ROOT/datasets/logs/detector_waves.pid"
sleep 2

echo "waves bash PID=$W_PID (datasets/logs/detector_waves.pid)"
echo "Лог: $LOG"
echo "Мониторинг: make detector-etl-progress-watch"
