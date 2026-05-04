#!/usr/bin/env bash
# Добор открытых слоёв к уже собранному EU-merge: merge (копии) + refine.
# EXTRA — каталоги с train/val[/test], имена классов должны маппиться в те же ключи, что и первый input
# (безопасно: вывод download_inaturalist.py или HF birds-525 scientific_common). Легаси-папки с «чужими»
# именами режут классы — не подставлять.
#
#   EXTRA="datasets/new/classifier/raw/source_inaturalist" \\
#     bash scripts/datasets/polish_eu_classifier.sh
#
set -euo pipefail
REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO"

ROOT="${1:-datasets/new/classifier}"
BASE="${ROOT}/yolo_cls_eu_merged"
PY="${PYTHON:-$REPO/.venv/bin/python}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PREV="${BASE}_prev_${STAMP}"

[[ -d "$BASE" ]] || { echo "missing $BASE"; exit 1; }

extra_raw="${EXTRA:-}"
if [[ -z "$extra_raw" ]]; then
  echo "Set EXTRA='path1 path2' with iNat / birds525 layers to merge"
  exit 1
fi
read -r -a EXTRA_INPUTS <<< "$extra_raw"

for p in "${EXTRA_INPUTS[@]}"; do
  rp="$p"
  [[ "$p" = /* ]] || rp="$REPO/$p"
  [[ -d "$rp" ]] || { echo "missing $rp"; exit 1; }
done

echo "==> backup $BASE -> $PREV"
mv "$BASE" "$PREV"

inputs=("$PREV")
for p in "${EXTRA_INPUTS[@]}"; do
  [[ "$p" = /* ]] && inputs+=("$p") || inputs+=("$REPO/$p")
done

echo "==> merge ${#inputs[@]} inputs -> $BASE"
"$PY" scripts/datasets/merge_classification_datasets.py \
  --inputs "${inputs[@]}" \
  --output "$BASE" \
  --val-ratio "${VAL_RATIO:-0.2}" \
  --restrict-to-primary-input

echo "==> refine"
"$PY" scripts/datasets/refine_classifier_yolo_cls.py \
  --root "$BASE" \
  --cache-dir "${ROOT}/.cache" \
  --dedupe --normalize --test-split

"$PY" scripts/datasets/refine_classifier_yolo_cls.py \
  --root "$BASE" \
  --dedupe-global-only --skip-rebalance

if [[ -f "$REPO/datasets/new/tools/build_manifests.py" ]]; then
  "$PY" "$REPO/datasets/new/tools/build_manifests.py" --task classifier --root "${ROOT}" || true
fi

echo "OK; previous tree: $PREV"
python3 - << PY
import os
root = "$BASE"
n = sum(1 for dp, _, fns in os.walk(root) for f in fns if f.lower().endswith((".jpg",".jpeg",".png",".webp")))
print("images:", n)
PY
