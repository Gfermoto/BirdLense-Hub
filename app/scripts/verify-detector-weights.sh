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

if [[ ! -d "$BASE/best_openvino_model" ]]; then
  echo "ERR: нет каталога $BASE/best_openvino_model" >&2
  exit 1
fi

echo "=== detector weights BASE=$BASE ==="
ls -la "$BASE" "$BASE/best_openvino_model/"
echo ""
echo "=== sha256sum ==="
sha256sum "$BASE/best.pt"
if [[ -f "$BASE/last.pt" ]]; then
  sha256sum "$BASE/last.pt"
fi
sha256sum \
  "$BASE/best_openvino_model/best.bin" \
  "$BASE/best_openvino_model/best.xml" \
  "$BASE/best_openvino_model/metadata.yaml"
echo ""

for f in best.bin best.xml metadata.yaml; do
  [[ -f "$BASE/best_openvino_model/$f" ]] || {
    echo "ERR: отсутствует $f" >&2
    exit 1
  }
done

grep -qE '^imgsz:|^\- 640' "$BASE/best_openvino_model/metadata.yaml" || true

echo "=== metadata names (YAML) ==="
grep -E '^(names:|  [0-9]+:|^    - 640)' "$BASE/best_openvino_model/metadata.yaml" || true
echo ""

if [[ -n "$REPO" && -f "$REPO/Makefile" ]]; then
  echo "=== make validate-weights (binary) ==="
  (cd "$REPO" && make validate-weights BINARY="$BASE/best.pt" 2>&1)
else
  echo "=== validate-weights: пропуск (нет репозитория с Makefile; обычно контейнер) ==="
  echo "    На VPS с полным деревом: запустите с хоста ~/BirdLense/app/scripts/$(basename "$0")"
fi

echo ""
echo "OK: комплект detector weights на месте."
