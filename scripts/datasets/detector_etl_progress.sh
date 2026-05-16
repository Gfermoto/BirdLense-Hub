#!/usr/bin/env bash
# Снимок прогресса ETL детектора (счётчики на диске, процессы, хвост лога волн).
# Запуск из корня репозитория или откуда угодно:
#   bash scripts/datasets/detector_etl_progress.sh
#   WATCH_INTERVAL=12 bash scripts/datasets/detector_etl_progress.sh watch
# Переменные: DETECTOR_ETL_ROOT, DETECTOR_WAVES_LOG, DETECTOR_WATCH_INTERVAL (или WATCH_INTERVAL)
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROOT="${DETECTOR_ETL_ROOT:-$REPO_ROOT/datasets/new/detector}"
BIN="$ROOT/binary"
LOG="${DETECTOR_WAVES_LOG:-$REPO_ROOT/datasets/logs/detector_waves.log}"
COCO_HOME="${FIFTYONE_DIR:-$HOME/fiftyone}/coco-2017"

count_jpg() {
  local d="${1:?}"
  if [[ ! -d "$d" ]]; then
    echo 0
    return
  fi
  find "$d" -type f \( -name '*.jpg' -o -name '*.jpeg' \) 2>/dev/null | wc -l
}

print_procs() {
  echo "--- процессы (bootstrap / waves) ---"
  local any=0
  if command -v pgrep >/dev/null 2>&1; then
    if pgrep -f 'bootstrap_detector_yolo\.py' >/dev/null 2>&1; then
      any=1
      echo "[bootstrap_detector_yolo.py]"
      pgrep -af 'bootstrap_detector_yolo\.py' 2>/dev/null | grep BirdLense | grep -Fv 'snap=' || true
    fi
    if pgrep -f 'build_detector_dataset_waves\.sh' >/dev/null 2>&1; then
      any=1
      echo "[build_detector_dataset_waves.sh]"
      pgrep -af "${REPO_ROOT}/scripts/datasets/build_detector_dataset_waves\.sh" 2>/dev/null | grep -Fv 'snap=' || \
        pgrep -af 'build_detector_dataset_waves\.sh' 2>/dev/null | grep -Fv 'snap='
    fi
  fi
  if [[ "$any" == 0 ]]; then
    echo "(активных pgrep-hit нет — проверь: ps aux | grep bootstrap_detector)"
  fi
}

show_once() {
  echo "======== $(date -Iseconds) ========="
  echo "DETECTOR_ETL_ROOT=$ROOT"
  [[ -r "$ROOT/dataset.yaml" ]] && echo "dataset.yaml OK" || echo "dataset.yaml (нет файла под корнем — это нормально, если только binary/)"
  echo
  echo "--- JPEG под binary/ ---"
  printf "%-26s %8s\n" "birds total" "$(count_jpg "$BIN/birds")"
  printf "%-26s %8s\n" "rodent total" "$(count_jpg "$BIN/rodent")"
  printf "%-26s %8s\n" "background total" "$(count_jpg "$BIN/background")"
  printf "%-26s %8s\n" "bg train/images" "$(count_jpg "$BIN/background/train/images")"
  printf "%-26s %8s\n" "bg val/images" "$(count_jpg "$BIN/background/val/images")"
  echo
  if [[ -d "$COCO_HOME/train" ]]; then
    local cf sz
    cf="$(find "$COCO_HOME/train" -type f -name '*.jpg' 2>/dev/null | wc -l)"
    sz="$(du -sh "$COCO_HOME/train" 2>/dev/null | cut -f1 || echo "?")"
    echo "--- кэш COCO (FiftyOne) train: ${cf} JPG, размер каталога $sz ---"
  else
    echo "--- кэш COCO train: каталог пока отсутствует ---"
  fi
  if [[ -f "$REPO_ROOT/datasets/logs/detector_waves.pid" ]]; then
    echo "--- pid из datasets/logs/detector_waves.pid: $(cat "$REPO_ROOT/datasets/logs/detector_waves.pid" | tr '\n' ' ') ---"
  fi
  echo
  print_procs
  echo
  if [[ -r "$LOG" ]]; then
    echo "--- последние осмысленные строки $LOG ($(wc -l <"$LOG") lines) ---"
    tail -600 "$LOG" | tr '\r' '\n' | grep -v '^[[:space:]]*$' | tail -30
  else
    echo "--- лог недоступен: $LOG ---"
  fi
}

watch_loop() {
  local interval="${WATCH_INTERVAL:-${DETECTOR_WATCH_INTERVAL:-15}}"
  while true; do
    clear 2>/dev/null || printf '\033[2J\033[H'
    show_once
    echo
    echo "Обновление каждые ${interval}s (Ctrl+C). WATCH_INTERVAL=… для интервала."
    sleep "${interval:?}"
  done
}

if [[ "${1:-}" == watch ]]; then
  watch_loop
else
  show_once
fi
