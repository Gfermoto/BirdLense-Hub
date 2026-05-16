#!/usr/bin/env bash
# Контроль объёма binary/: птицы и грызуны не ниже плана больших волн (A+B+C).
# Абсолютная «гарантия по каждому пикселю» недостижима — это порог по числам + опционально лог.
#
# Из корня репо или с явным корнем детектора:
#   DETECTOR_ETL_ROOT=… bash scripts/datasets/verify_detector_binary_inventory.sh
# Дополнительно хвост лога известных тегов (нужен ripgrep если есть):
#   DETECTOR_LOG_SCAN=1 DETECTOR_ETL_ROOT=… bash scripts/datasets/verify_detector_binary_inventory.sh
#
# Пороги по умолчанию = суммарная цель build_detector_dataset_waves.sh после 5×5×5 проходов A,B,C:
#   птицы COCO train 2500, val ~700 только COCO но в сумме с OID val 2500 → val минимум 3200 JPEG;
#   грызуны train 3500, val 900.
# Перебить: MIN_BIRD_TRAIN, MIN_BIRD_VAL, MIN_ROD_TRAIN, MIN_ROD_VAL.
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ROOT="${DETECTOR_ETL_ROOT:-$REPO_ROOT/datasets/new/detector}"
BIN="$ROOT/binary"
LOG="${DETECTOR_ETL_VERIFY_LOG:-$REPO_ROOT/datasets/logs/detector_waves.log}"

MIN_BT="${MIN_BIRD_TRAIN:-2500}"
MIN_BV="${MIN_BIRD_VAL:-3200}"
MIN_RT="${MIN_ROD_TRAIN:-3500}"
MIN_RV="${MIN_ROD_VAL:-900}"

count_jpeg() {
  local d="$1"
  if [[ ! -d "$d" ]]; then
    echo 0
    return
  fi
  find "$d" -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) 2>/dev/null | wc -l
}

FAILED=0
check_min() {
  local label=$1 got=$2 min=$3
  printf '%-36s %-7s минимум %s\n' "$label:" "$got" "$min"
  got=${got:-0}
  got=${got// /}
  if (( got < min )); then
    FAILED=1
  fi
}

echo "CORR: $ROOT"
echo "JPEG (минимумы по плану A+B+C):"
check_min "birds train/images" "$(count_jpeg "$BIN/birds/train/images")" "$MIN_BT"
check_min "birds val/images" "$(count_jpeg "$BIN/birds/val/images")" "$MIN_BV"
check_min "rodent train/images" "$(count_jpeg "$BIN/rodent/train/images")" "$MIN_RT"
check_min "rodent val/images" "$(count_jpeg "$BIN/rodent/val/images")" "$MIN_RV"

btw=$(count_jpeg "$BIN/birds/test/images")
if [[ "${btw:-0}" != "0" ]]; then
  printf '%-36s доп. JPEG: %s (вне двух основных splits волн)\n' "birds test/images:" "$btw"
fi

echo ""

if [[ "${DETECTOR_LOG_SCAN:-0}" == "1" ]]; then
  if [[ ! -r "$LOG" ]]; then
    echo "Лог недоступен: $LOG (пропуск DETECTOR_LOG_SCAN)"
  elif command -v rg >/dev/null 2>&1; then
    echo "Подсказки по логу (rg, последние совпадения):"
    rg -n '^\[birds\]|\[birds-oid\]|\[rodent\]|предупреждение:|стоп:|прерываем сплит' "$LOG" 2>/dev/null | tail -25 || true
    echo "---"
  else
    echo "Подсказки по логу (grep без rg):"
    grep -nE '^\[birds\]|^\[birds-oid\]|^\[rodent\]|предупреждение:|стоп:|прерываем сплит' "$LOG" 2>/dev/null | tail -25 || true
    echo "---"
  fi

  SC=0
  SC=$(grep -cE '(стоп:|прерываем сплит)' "$LOG" 2>/dev/null || true)
  SC=${SC:-0}
  printf 'Строк «стоп|прерывание сплита» в логе: %s (большое число — разберись вручную по контексту)\n' "$SC"
  echo ""
fi

if [[ "$FAILED" != 0 ]]; then
  echo >&2 \
    "FAIL: ниже порога. Добор: см. Makefile bootstrap-detector-data с ARGS, или точечный bootstrap_detector_yolo.py --root … только с недостачей (частичный skip-background)." \
    "Не перезатирай случайно: дубликаты по имени кадра пропускаются."
  exit 1
fi

echo "PASS: числовой гейт A+B+C (train/val JPEG выше минимумов)."
exit 0
