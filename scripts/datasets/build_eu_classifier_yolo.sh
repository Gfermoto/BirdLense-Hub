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

echo "==> Merge (копии файлов; --symlink ломает объём при refine/rebalance)"
"${PY}" scripts/datasets/merge_classification_datasets.py \
  --inputs "${ROOT}/yolo_cls_eu_hf" \
  --output "${ROOT}/yolo_cls_eu_merged" \
  --val-ratio 0.2

echo "==> Refine: dedupe + normalize + test (имена Scientific_(Common) как в Hub)"
"${PY}" scripts/datasets/refine_classifier_yolo_cls.py \
  --root "${ROOT}/yolo_cls_eu_merged" \
  --cache-dir "${ROOT}/.cache" \
  --dedupe --normalize --test-split

# Добор редких классов без урезания «толстых»: см. backfill_classifier_open.py и EU_CLASSIFIER.md.
# Урезание датасета (subsampling): только если нужно вручную — scripts/datasets/balance_classifier_yolo_cls.py (не в этом скрипте).

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
