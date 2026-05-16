#!/usr/bin/env bash
# Добор binary/rodent до прохождения verify_detector_binary_inventory.sh при плохой сети:
# каждый раунд добавляет только недостающее (bootstrap считает уже лежащие JPEG).
#
# Из корня репо:
#   bash scripts/datasets/bootstrap_rodents_until_verify.sh
#
# Переменные:
#   DETECTOR_ETL_ROOT  — корень детектора (default: <repo>/datasets/new/detector)
#   BIRDLENSE_PYTHON   — интерпретатор (default: <repo>/.venv/bin/python)
#   MAX_ROUNDS         — максимум итераций (default: 500)
#   SLEEP_SEC          — пауза между раундами (default: 20)
#   CHUNK_SIZE         — если задано — передаётся как --chunk-size
#   RODENT_TRAIN, RODENT_VAL — квоты (defaults: 3500 900 для гейта A+B+C)
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROOT="${DETECTOR_ETL_ROOT:-$REPO_ROOT/datasets/new/detector}"
PY="${BIRDLENSE_PYTHON:-$REPO_ROOT/.venv/bin/python}"
VERIFY="$SCRIPT_DIR/verify_detector_binary_inventory.sh"
LOG_DIR="$REPO_ROOT/datasets/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/rodent_until_verify.log"

MAX_ROUNDS="${MAX_ROUNDS:-500}"
SLEEP_SEC="${SLEEP_SEC:-20}"
RT="${RODENT_TRAIN:-3500}"
RV="${RODENT_VAL:-900}"

export BIRDLENSE_BOOTSTRAP_ZOO_RETRIES="${BIRDLENSE_BOOTSTRAP_ZOO_RETRIES:-20}"
export BIRDLENSE_BOOTSTRAP_CHUNK_MAX="${BIRDLENSE_BOOTSTRAP_CHUNK_MAX:-80}"

_round=0
echo "repo=$REPO_ROOT root=$ROOT py=$PY max_rounds=$MAX_ROUNDS" | tee -a "$LOG"

while ((_round < MAX_ROUNDS)); do
  _round=$((_round + 1))
  echo "===== $(date -Is) round $_round =====" | tee -a "$LOG"
  CHUNK_ARGS=()
  if [[ -n "${CHUNK_SIZE:-}" ]]; then
    CHUNK_ARGS=(--chunk-size "$CHUNK_SIZE")
  fi
  # shellcheck disable=SC2086
  "$PY" "$SCRIPT_DIR/bootstrap_detector_yolo.py" \
    --root "$ROOT" \
    --skip-birds \
    --skip-background \
    --rodent-train "$RT" \
    --rodent-val "$RV" \
    "${CHUNK_ARGS[@]}" \
    2>&1 | tee -a "$LOG"

  if DETECTOR_ETL_ROOT="$ROOT" bash "$VERIFY"; then
    echo "PASS verify (round $_round)" | tee -a "$LOG"
    exit 0
  fi
  echo "verify still FAIL — sleep ${SLEEP_SEC}s …" | tee -a "$LOG"
  sleep "$SLEEP_SEC"
done

echo "STOP: достигнут MAX_ROUNDS=$MAX_ROUNDS без PASS verify (смотри $LOG)" | tee -a "$LOG"
exit 1
