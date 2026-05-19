#!/usr/bin/env bash
# Behavior v2.1 — extract → balance report → train → export → canary gate (run on VPS in container).
set -euo pipefail

ROOT="${ROOT:-/app}"
DB="${DB:-/app/data/db/birdlense.db}"
OUT_ROOT="${OUT_ROOT:-/app/data/datasets/behavior_v2_1}"
MANIFEST="${MANIFEST:-$OUT_ROOT/behavior_dataset_v2.1.json}"
CROPS_DIR="${CROPS_DIR:-$OUT_ROOT/crops}"
ARTIFACTS="${ARTIFACTS:-$OUT_ROOT/artifacts}"
OV_DIR="${OV_DIR:-/app/processor/models/behavior_v2_1_openvino}"
MIN_CONF="${MIN_CONF:-0.85}"
MIN_LABEL_COUNT="${MIN_LABEL_COUNT:-3}"
BACKBONE="${BACKBONE:-x3d}"
AUGMENT_COPIES="${AUGMENT_COPIES:-4}"

cd "$ROOT"
export PYTHONPATH="$ROOT/scripts:$ROOT"

echo "=== [1/5] Extract prod labeled tracklets ==="
python3 scripts/ml_behavior_extract_prod_labeled.py \
  --db "$DB" \
  --out "$MANIFEST" \
  --crops-dir "$CROPS_DIR" \
  --repo-root "$ROOT" \
  --min-confidence "$MIN_CONF" \
  --min-blur-score 4 \
  --min-label-count "$MIN_LABEL_COUNT"

python3 - <<'PY'
import json
from pathlib import Path
import os
m = json.loads(Path(os.environ["MANIFEST"]).read_text())
print("tracklet_count:", m.get("tracklet_count"))
print("label_counts:", m.get("label_counts"))
print("split_counts:", m.get("split_counts"))
flying = int((m.get("label_counts") or {}).get("flying", 0))
if flying < 10:
    print("WARNING: flying samples < 10 — consider WetlandBirds import or ml_behavior_augment before train")
PY

echo "=== [2/5] Train video model v2.1 ==="
python3 scripts/ml_behavior_train_video.py \
  --manifest "$MANIFEST" \
  --backbone "$BACKBONE" \
  --out-dir "$ARTIFACTS" \
  --augment-copies "$AUGMENT_COPIES"

EXPORT_JSON=$(ls -1t "$ARTIFACTS"/behavior_video_export@*.json 2>/dev/null | head -1)
test -n "$EXPORT_JSON" || { echo "No behavior_video_export@*.json in $ARTIFACTS" >&2; exit 1; }

echo "=== [3/5] Export OpenVINO FP16 ==="
python3 scripts/ml_behavior_export_video_openvino.py \
  --video-export "$EXPORT_JSON" \
  --out-dir "$OV_DIR" \
  --precision fp16

echo "=== [4/5] Canary replay gate (offline) ==="
if command -v make >/dev/null 2>&1 && [ -f Makefile ]; then
  MANIFEST="$MANIFEST" make ml-behavior-canary-gate || true
fi

echo "=== [5/5] Summary ==="
echo "Manifest: $MANIFEST"
echo "OpenVINO: $OV_DIR"
echo "Next: server-apply-user-config-patch for canary v2.1, then 24–48h metrics before engine:auto"
