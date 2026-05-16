#!/usr/bin/env bash
# Рекомендуемый «большой» bootstrap для трёхклассового детектора (редактируй числа).
# Требуется: pip install fiftyone pyyaml, место на диске, сеть.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

python3 bootstrap_detector_yolo.py \
  --birds-train 2500 \
  --birds-val 700 \
  --birds-oid-train 0 \
  --birds-oid-val 2500 \
  --birds-oid-validation-only \
  --rodent-train 3500 \
  --rodent-val 900 \
  --background-train 4500 \
  --background-val 1200 \
  --background-hard-train 1800 \
  --background-hard-val 500 \
  --chunk-size 40 \
  --bg-scan-chunk 800

echo "==> merge (repo root: $REPO_ROOT)"
cd "$REPO_ROOT"
make dataset-merge-three-class
echo "OK: scripts/datasets/binary/merged/"
