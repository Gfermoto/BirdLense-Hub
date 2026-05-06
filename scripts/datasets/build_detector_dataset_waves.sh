#!/usr/bin/env bash
# Тот же объём, что build_detector_dataset_large.sh, но порциями (волнами).
# Меньше пик памяти/сети; между волнами пауза — можно Ctrl+C и продолжить позже.
#
# Скачивание пишет в datasets/new/detector/binary/ (см. DETECTOR_ETL_ROOT / --root).
# После всех фаз: из корня репозитория «make dataset-merge-three-class» → datasets/new/detector/yolo/
#
#   bash scripts/datasets/build_detector_dataset_waves.sh
#   WAVE_PAUSE=10 bash scripts/datasets/build_detector_dataset_waves.sh
#   RUN_MERGE=1 bash scripts/datasets/build_detector_dataset_waves.sh
#
# Только птицы + грызуны (без фона D/E), фон добить позже:
#   DETECTOR_PHASE_END=3 bash scripts/datasets/build_detector_dataset_waves.sh
#
# Продолжить после прерывания (пропуск ранних фаз):
#   DETECTOR_PHASE_BEGIN=4 bash scripts/datasets/build_detector_dataset_waves.sh   # только D+E
# Нумерация: 1=A, 2=B, 3=C, 4=D, 5=E.
# Если оборвалась последняя волна фазы C, добейте недостаток одиночным запуском, например:
#   PYTHON=python3 python bootstrap_detector_yolo.py --skip-birds --skip-background \
#     --rodent-train 140 --rodent-val 180
# (подставьте недостающие квоты к целевым 700/180 за один проход этого скрипта.)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

if [[ -z "${PYTHON:-}" && -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif [[ -z "${PYTHON:-}" ]]; then
  PYTHON="python3"
fi

PAUSE="${WAVE_PAUSE:-5}"
CHUNK="${CHUNK_SIZE:-35}"
# Крупнее chunk для фаз птиц/грызунов — реже порции только из уже скопированных имён (_copy_once).
CHUNK_PHASE_A="${CHUNK_PHASE_A:-280}"
CHUNK_PHASE_B="${CHUNK_PHASE_B:-220}"
CHUNK_PHASE_C="${CHUNK_PHASE_C:-180}"
BGCH="${BG_SCAN_CHUNK:-500}"
PHASE_BEGIN="${DETECTOR_PHASE_BEGIN:-1}"
# 1…5 = A…E; по умолчанию все фазы. Пример: DETECTOR_PHASE_END=3 — остановиться после rodent (C), без фона.
PHASE_END="${DETECTOR_PHASE_END:-5}"
if ! [[ "$PHASE_END" =~ ^[1-5]$ ]] || (( PHASE_END < PHASE_BEGIN )); then
  echo "Invalid DETECTOR_PHASE_BEGIN/END: begin=$PHASE_BEGIN end=$PHASE_END (need 1..5, end>=begin)" >&2
  exit 1
fi
DETECTOR_ETL_ROOT="${DETECTOR_ETL_ROOT:-$REPO_ROOT/datasets/new/detector}"
# Больше pool / chunk — чаще находим кадры без bird (медленнее на батч, меньше «нулевых» волн).
EXTRA_BG_POOL=()
[[ -n "${DETECTOR_BG_TRAIN_POOL:-}" ]] && EXTRA_BG_POOL+=(--background-train-pool "${DETECTOR_BG_TRAIN_POOL}")
[[ -n "${DETECTOR_BG_VAL_POOL:-}" ]] && EXTRA_BG_POOL+=(--background-val-pool "${DETECTOR_BG_VAL_POOL}")

say() { echo ""; echo ">>> $*"; echo ""; }

pause() {
  echo "(пауза ${PAUSE}s; Ctrl+C — стоп между волнами)"
  sleep "$PAUSE"
}

run_py() {
  "$PYTHON" bootstrap_detector_yolo.py --root "$DETECTOR_ETL_ROOT" "$@"
}

if (( PHASE_BEGIN <= 1 && PHASE_END >= 1 )); then
# --- A: COCO bird → ~2500 train / 700 val ---
say "Фаза A: COCO bird (5×500 train + 140 val)"
for i in 1 2 3 4 5; do
  say "A$i/5"
  run_py \
    --birds-train 500 --birds-val 140 \
    --skip-birds-oid \
    --skip-rodents \
    --skip-background \
    --chunk-size "$CHUNK_PHASE_A"
  pause
done
fi

if (( PHASE_BEGIN <= 2 && PHASE_END >= 2 )); then
# --- B: OID Bird validation-only; при oid-train=0 всё уходит в val-папку ---
say "Фаза B: Open Images Bird (5×500, validation-only → val/)"
for i in 1 2 3 4 5; do
  say "B$i/5"
  run_py \
    --birds-train 0 --birds-val 0 \
    --birds-oid-train 0 --birds-oid-val 500 \
    --birds-oid-validation-only \
    --skip-birds-coco \
    --skip-rodents \
    --skip-background \
    --chunk-size "$CHUNK_PHASE_B"
  pause
done
fi

if (( PHASE_BEGIN <= 3 && PHASE_END >= 3 )); then
# --- C: Rodent → ~3500 / 900 ---
say "Фаза C: Rodent (5×700 train + 180 val)"
for i in 1 2 3 4 5; do
  say "C$i/5"
  run_py \
    --skip-birds \
    --skip-background \
    --rodent-train 700 --rodent-val 180 \
    --chunk-size "$CHUNK_PHASE_C"
  pause
done
fi

if (( PHASE_BEGIN <= 4 && PHASE_END >= 4 )); then
# --- D: фон простой → ~4500 / 1200 ---
say "Фаза D: background soft (5×900 train + 240 val)"
for i in 1 2 3 4 5; do
  say "D$i/5"
  run_py \
    --skip-birds \
    --skip-rodents \
    --skip-background-hard \
    --background-train 900 --background-val 240 \
    --background-hard-train 0 --background-hard-val 0 \
    "${EXTRA_BG_POOL[@]}" \
    --chunk-size "$CHUNK" \
    --bg-scan-chunk "$BGCH"
  pause
done
fi

if (( PHASE_BEGIN <= 5 && PHASE_END >= 5 )); then
# --- E: hard-negative → 1800 / 500 ---
say "Фаза E: background hard (4×450 train + 125 val)"
for i in 1 2 3 4; do
  say "E$i/4"
  run_py \
    --skip-birds \
    --skip-rodents \
    --skip-background-soft \
    --background-train 0 --background-val 0 \
    --background-hard-train 450 --background-hard-val 125 \
    "${EXTRA_BG_POOL[@]}" \
    --chunk-size "$CHUNK" \
    --bg-scan-chunk "$BGCH"
  pause
done
fi

say "Готово → datasets/new/detector/binary/{birds,rodent,background}/"
if [[ "${RUN_MERGE:-}" == "1" ]]; then
  say "RUN_MERGE=1 → make dataset-merge-three-class"
  cd "$REPO_ROOT"
  make dataset-merge-three-class
fi

# Полный ETL (включая фон E) — маркер для watchdog. Частичный прогон — без .detector_etl_done.
if (( PHASE_END >= 5 )); then
  touch "$REPO_ROOT/datasets/logs/.detector_etl_done"
  echo "ETL_WAVES_FINISHED ok $(date -Is) (phases 1–5)"
else
  echo "ETL_WAVES_PARTIAL phases ${PHASE_BEGIN}-${PHASE_END} ok $(date -Is) — без фона? задай DETECTOR_PHASE_END=5 и продолжи с PHASE_BEGIN"
fi
