#!/usr/bin/env bash
# Сборка EU-приоритетного классификатора без вырезания классов.
# ROOT — корень под datasets/new/classifier (или свой путь).
set -euo pipefail

ROOT="${1:-datasets/new/classifier}"
PY="${PYTHON:-python3}"

echo "==> EU HF base -> ${ROOT}/yolo_cls_eu_hf"
"${PY}" scripts/datasets/download_birds_eu_merged.py --output "${ROOT}/yolo_cls_eu_hf"

echo "==> Optional: bulk iNaturalist EU (раскомментируйте и задайте max-obs)"
# "${PY}" scripts/datasets/download_inaturalist.py \
#   --output "${ROOT}/raw/inat_europe_bulk" \
#   --max-obs 40000 \
#   --photo-size medium

echo "==> Merge (только HF base; добавьте второй input если скачали iNat)"
"${PY}" scripts/datasets/merge_classification_datasets.py \
  --inputs "${ROOT}/yolo_cls_eu_hf" \
  --output "${ROOT}/yolo_cls_eu_merged" \
  --symlink \
  --val-ratio 0.2

echo "==> Refine: dedupe + normalize + test (имена Scientific_(Common) как в Hub)"
"${PY}" scripts/datasets/refine_classifier_yolo_cls.py \
  --root "${ROOT}/yolo_cls_eu_merged" \
  --cache-dir "${ROOT}/.cache" \
  --dedupe --normalize --test-split

if [[ "${CLASSIFIER_BALANCE:-}" == "1" ]]; then
  echo "==> Balance (CLASSIFIER_BALANCE=1): min=${BALANCE_MIN_IMAGES:-12} ratio=${BALANCE_MAX_RATIO:-6} anchor_p=${BALANCE_ANCHOR_PCT:-5}"
  "${PY}" scripts/datasets/balance_classifier_yolo_cls.py \
    --root "${ROOT}/yolo_cls_eu_merged" \
    --min-images "${BALANCE_MIN_IMAGES:-12}" \
    --max-ratio "${BALANCE_MAX_RATIO:-6}" \
    --anchor-percentile "${BALANCE_ANCHOR_PCT:-5}" \
    --seed "${BALANCE_SEED:-42}" \
    --report-json "${ROOT}/balance_report.json"
fi

"${PY}" scripts/datasets/refine_classifier_yolo_cls.py \
  --root "${ROOT}/yolo_cls_eu_merged" \
  --dedupe-global-only --skip-rebalance

echo "==> Manifest (если есть datasets/new/tools/build_manifests.py)"
REPO="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
if [[ -f "${REPO}/datasets/new/tools/build_manifests.py" ]]; then
  "${PY}" "${REPO}/datasets/new/tools/build_manifests.py" \
    --task classifier \
    --root "${ROOT}"
fi

echo "OK: ${ROOT}/yolo_cls_eu_merged"
