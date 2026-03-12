#!/bin/bash
# Скачать birds-525 и iNaturalist Europe, объединить.

set -e
cd "$(dirname "$0")/../.."
VENV="${VENV:-.venv-datasets}"
OUT="${OUT:-datasets}"

# venv
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q datasets huggingface_hub tqdm Pillow requests
fi

mkdir -p "$OUT"

echo "=== 1. birds-525-species (~18k, ~280MB) ==="
"$VENV/bin/python" scripts/datasets/download_hf_birds.py \
  --dataset 34data/birds-525-species \
  --output "$OUT/birds_525_cls" \
  --val-ratio 0.2

echo "=== 2. iNaturalist Europe (~2k obs, ~1 ч) ==="
"$VENV/bin/python" scripts/datasets/download_inaturalist.py \
  --output "$OUT/inaturalist_europe_cls" \
  --max-obs 2000 \
  --val-ratio 0.2

echo "=== 3. Объединение ==="
"$VENV/bin/python" scripts/datasets/merge_classification_datasets.py \
  --inputs "$OUT/birds_525_cls" "$OUT/inaturalist_europe_cls" \
  --output "$OUT/merged_cls" \
  --val-ratio 0.2

echo "=== Готово: $OUT/merged_cls ==="
du -sh "$OUT/merged_cls"
