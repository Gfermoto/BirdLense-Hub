#!/usr/bin/env bash
# Сверка бинарных весов + OpenVINO IR (+ make validate на хосте с полным деревом репо).
#
# Из корня репозитория (старый путь-симлинк):
#   scripts/verify-detector-weights.sh
# Из папки app/scripts (деплоится в образ):
#   ./verify-detector-weights.sh
# На VPS после rsync:
#   ~/BirdLense/app/scripts/verify-detector-weights.sh
# В контейнере (только хэши + metadata; без make):
#   docker exec birdlense /app/scripts/verify-detector-weights.sh

set -euo pipefail

_SCR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO=""
if [[ "$_SCR" == "/app/scripts" ]]; then
  REPO=""
  BASE="${BASE:-/app/processor/models/detection/weights}"
elif [[ "$(basename "$_SCR")" == "scripts" && "$(basename "$(dirname "$_SCR")")" == "app" ]]; then
  REPO="$(cd "$_SCR/../.." && pwd)"
  BASE="${BASE:-$REPO/app/processor/models/detection/weights}"
else
  REPO="$(cd "$_SCR/.." && pwd)"
  BASE="${BASE:-$REPO/app/processor/models/detection/weights}"
fi

PT_FILE="${PT_FILE:-$BASE/trapper_ai_v02_2024.pt}"
OV_DIR="${OV_DIR:-$BASE/trapper_ai_v02_2024_openvino_model}"

if [[ ! -f "$PT_FILE" ]]; then
  echo "ERR: нет файла $PT_FILE" >&2
  exit 1
fi
if [[ ! -d "$OV_DIR" ]]; then
  echo "ERR: нет каталога $OV_DIR" >&2
  exit 1
fi

echo "=== detector weights BASE=$BASE ==="
ls -la "$BASE" "$OV_DIR/"
echo ""
echo "=== sha256sum ==="
sha256sum "$PT_FILE"
sha256sum \
  "$OV_DIR/best.bin" \
  "$OV_DIR/best.xml"
if [[ -f "$OV_DIR/metadata.yaml" ]]; then
  sha256sum "$OV_DIR/metadata.yaml"
fi
echo ""

for f in best.bin best.xml; do
  [[ -f "$OV_DIR/$f" ]] || {
    echo "ERR: отсутствует $f" >&2
    exit 1
  }
done

if [[ -f "$OV_DIR/metadata.yaml" ]]; then
  grep -qE '^imgsz:|^\- 640|^\- 960|^\- 1024' "$OV_DIR/metadata.yaml" || true
  echo "=== metadata names (YAML) ==="
  grep -E '^(names:|  [0-9]+:|^    - 640|^    - 960|^    - 1024)' "$OV_DIR/metadata.yaml" || true
  echo ""
fi

if [[ -n "$REPO" && -f "$REPO/Makefile" ]]; then
  echo "=== make validate-weights (binary) ==="
  (cd "$REPO" && make validate-weights BINARY="$PT_FILE" 2>&1)
else
  echo "=== validate-weights: пропуск (нет репозитория с Makefile; обычно контейнер) ==="
  echo "    На VPS с полным деревом: запустите с хоста ~/BirdLense/app/scripts/$(basename "$0")"
fi

echo ""
echo "OK: комплект detector weights на месте."
