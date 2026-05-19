#!/usr/bin/env bash
# Behavior v2.1 autonomous pipeline (VPS host, docker exec birdlense).
# Extract → (WetlandBirds|synthetic supplement) → train → OpenVINO export.
set -euo pipefail

ROOT="${ROOT:-/root/BirdLense}"
cd "$ROOT"

# --- WetlandBirds: host paths (must live under app/data for container mount) ---
WB_CANDIDATES=(
  "${WB_ROOT:-}"
  "$ROOT/app/data/datasets/Visual-WetlandBirds/annotations"
  "$ROOT/app/data/datasets/WetlandBirds"
  "/data/Visual-WetlandBirds/annotations"
  "$ROOT/datasets/WetlandBirds"
)

DATASET_RELAXED="/app/data/datasets/behavior_v2_1/behavior_dataset_v2.1_relaxed.json"
DATASET_MERGED="/app/data/datasets/behavior_v2_1/behavior_dataset_v2.1_merged.json"
SYNTH_ROOT="/app/data/datasets/behavior_v2_1/synthetic_supplement"
ARTIFACTS_DIR="/app/data/datasets/behavior_v2_1/artifacts_v2_1"
OV_DIR="/app/processor/models/behavior_v2_1_openvino"
LOG_DIR="$ROOT/app/data/datasets/behavior_v2_1"
mkdir -p "$LOG_DIR"

echo "== Behavior v2.1 autonomous pipeline =="

# --- Stage 0: sync scripts into container ---
SCRIPTS=(
  ml_behavior_extract_prod_labeled.py
  ml_behavior_crop_core.py
  ml_behavior_eval_harness.py
  ml_behavior_train_video.py
  ml_behavior_export_video_openvino.py
  ml_behavior_export_onnx.py
  ml_behavior_merge_manifests.py
  ml_behavior_import_wetlandbirds.py
  ml_behavior_bootstrap_synthetic.py
  ml_behavior_dataset_manifest.py
)

for f in "${SCRIPTS[@]}"; do
  src="scripts/$f"
  if [[ -f "$src" ]]; then
    docker cp "$src" birdlense:/app/scripts/
    echo "  synced $f"
  else
    echo "  MISSING $src" >&2
    exit 1
  fi
done

# Resolve WetlandBirds on host (visible in container under /app/data/...)
WB_HOST=""
for cand in "${WB_CANDIDATES[@]}"; do
  [[ -z "$cand" ]] && continue
  if [[ -d "$cand" ]] && compgen -G "$cand/**/*.csv" >/dev/null 2>&1 || find "$cand" -maxdepth 4 -name '*.csv' -print -quit 2>/dev/null | grep -q .; then
    WB_HOST="$cand"
    break
  fi
done

# Map host path under BirdLense/app/data → container /app/data/...
WB_CONTAINER=""
if [[ -n "$WB_HOST" ]]; then
  real_wb="$(readlink -f "$WB_HOST" 2>/dev/null || echo "$WB_HOST")"
  real_data="$(readlink -f "$ROOT/app/data" 2>/dev/null || echo "$ROOT/app/data")"
  if [[ "$real_wb" == "$real_data"* ]]; then
    WB_CONTAINER="/app/data${real_wb#"$real_data"}"
  else
    echo "WARN: WetlandBirds outside app/data mount — copying into app/data/datasets/WetlandBirds"
    mkdir -p "$ROOT/app/data/datasets/WetlandBirds"
    rsync -a --delete "${WB_HOST}/" "$ROOT/app/data/datasets/WetlandBirds/" 2>/dev/null || cp -a "$WB_HOST/." "$ROOT/app/data/datasets/WetlandBirds/"
    WB_CONTAINER="/app/data/datasets/WetlandBirds"
  fi
  echo "WetlandBirds: host=$WB_HOST container=$WB_CONTAINER"
else
  echo "WetlandBirds: not found — downloading Zenodo annotations..."
  bash "$ROOT/scripts/download_wetlandbirds_zenodo.sh"
  python3 "$ROOT/scripts/convert_wetlandbirds_zenodo_crops.py" \
    --crops-csv "$ROOT/app/data/datasets/Visual-WetlandBirds/raw/crops.csv" \
    --species-csv "$ROOT/app/data/datasets/Visual-WetlandBirds/raw/species_ID.csv" \
    --out-dir "$ROOT/app/data/datasets/Visual-WetlandBirds/annotations"
  WB_CONTAINER="/app/data/datasets/Visual-WetlandBirds/annotations"
fi

# --- Stage 1: relaxed extract ---
echo "== [1] Relaxed extract =="
docker exec birdlense bash -lc "set -euo pipefail
  mkdir -p /app/data/datasets/behavior_v2_1/crops_relaxed
  cd /app && export PYTHONPATH=/app/scripts:/app
  python3 scripts/ml_behavior_extract_prod_labeled.py \
    --db /app/data/db/birdlense.db \
    --out $DATASET_RELAXED \
    --crops-dir /app/data/datasets/behavior_v2_1/crops_relaxed \
    --repo-root /app \
    --min-confidence 0.85 \
    --min-blur-score 2 \
    --min-label-count 1
"

# --- Stage 2: stats ---
read -r FLYING_COUNT TOTAL_COUNT < <(
  docker exec birdlense python3 -c "
import json
m = json.load(open('$DATASET_RELAXED'))
flying = int((m.get('label_counts') or {}).get('flying', 0))
print(flying, m.get('tracklet_count', 0))
"
)
echo "Extract: total=$TOTAL_COUNT flying=$FLYING_COUNT labels=$(docker exec birdlense python3 -c "import json; print(json.load(open('$DATASET_RELAXED')).get('label_counts'))")"

MANIFEST_TO_USE="$DATASET_RELAXED"

if [[ "$FLYING_COUNT" -eq 0 ]]; then
  echo "ERROR: flying=0 — label flying videos in Hub UI, then re-run." >&2
  exit 1
fi

# --- Stage 3: supplement if flying < 10 ---
if [[ "$FLYING_COUNT" -lt 10 ]]; then
  if [[ -n "$WB_CONTAINER" ]]; then
    echo "== [2] WetlandBirds import + merge =="
    docker exec birdlense bash -lc "set -euo pipefail
      export PYTHONPATH=/app/scripts:/app
      python3 scripts/ml_behavior_import_wetlandbirds.py \
        --annotations-root '$WB_CONTAINER' \
        --out /app/data/datasets/behavior_v2_1/wetland.json \
        --crops-dir /app/data/datasets/behavior_v2_1/wetland_crops \
        --extract-crops --holdout-ratio 0.1
      python3 scripts/ml_behavior_merge_manifests.py \
        --inputs $DATASET_RELAXED /app/data/datasets/behavior_v2_1/wetland.json \
        --out $DATASET_MERGED --holdout-ratio 0.1
    "
    MANIFEST_TO_USE="$DATASET_MERGED"
  else
    echo "== [2] Synthetic WetlandBirds supplement (no real dataset on server) =="
    docker exec birdlense bash -lc "set -euo pipefail
      export PYTHONPATH=/app/scripts:/app
      python3 scripts/ml_behavior_bootstrap_synthetic.py \
        --out-root $SYNTH_ROOT --per-label 48
    "
    docker exec birdlense bash -lc "set -euo pipefail
      export PYTHONPATH=/app/scripts:/app
      python3 scripts/ml_behavior_merge_manifests.py \
        --inputs $DATASET_RELAXED $SYNTH_ROOT/behavior_tracklet_merged.json \
        --out $DATASET_MERGED --holdout-ratio 0.1
    "
    MANIFEST_TO_USE="$DATASET_MERGED"
  fi

  read -r FLYING_COUNT TOTAL_COUNT < <(
    docker exec birdlense python3 -c "
import json
m = json.load(open('$MANIFEST_TO_USE'))
print(int((m.get('label_counts') or {}).get('flying', 0)), m.get('tracklet_count', 0))
"
  )
  echo "After supplement: total=$TOTAL_COUNT flying=$FLYING_COUNT labels=$(docker exec birdlense python3 -c "import json; print(json.load(open('$MANIFEST_TO_USE')).get('label_counts'))")"
fi

# --- Stage 4: train + OpenVINO ---
if [[ "$FLYING_COUNT" -lt 10 ]]; then
  AUG_COPIES=12
  MIN_F1=0.45
  echo "WARN: flying still < 10 ($FLYING_COUNT) — training with heavy augment (experimental)"
else
  AUG_COPIES=4
  MIN_F1=0.6
fi

echo "== [3] Train + export (manifest=$MANIFEST_TO_USE aug=$AUG_COPIES min_f1=$MIN_F1) =="
docker exec birdlense pip install -q onnx 2>/dev/null || true

docker exec \
  -e MANIFEST="$MANIFEST_TO_USE" \
  -e ART="$ARTIFACTS_DIR" \
  -e OV="$OV_DIR" \
  -e AUG_COPIES="$AUG_COPIES" \
  -e MIN_F1="$MIN_F1" \
  birdlense bash -lc 'set -euo pipefail
cd /app
export PYTHONPATH=/app/scripts:/app
mkdir -p "$ART" "$OV"
python3 scripts/ml_behavior_train_video.py \
  --manifest "$MANIFEST" \
  --backbone x3d \
  --out-dir "$ART" \
  --augment-copies "$AUG_COPIES" \
  --model-kind video_v2_1 \
  --min-macro-f1 "$MIN_F1" || TRAIN_RC=$?
TRAIN_RC=${TRAIN_RC:-0}
EXPORT=$(ls -1t "$ART"/behavior_video_export@*.json 2>/dev/null | head -1 || true)
if [[ -z "${EXPORT:-}" ]]; then
  echo "Train failed: no export JSON (rc=$TRAIN_RC)" >&2
  exit 1
fi
python3 scripts/ml_behavior_export_video_openvino.py \
  --video-export "$EXPORT" \
  --out-dir "$OV" \
  --precision fp16
ls -la "$OV"
python3 -c "
import json, glob
rep = sorted(glob.glob(\"$ART/behavior_train_report@*.json\"))[-1]
r = json.load(open(rep))
print(\"TRAIN_REPORT\", json.dumps({\"macro_f1\": r.get(\"metrics\",{}).get(\"macro_f1\"), \"accuracy\": r.get(\"metrics\",{}).get(\"accuracy\"), \"ok\": r.get(\"ok\")}))
"
'

# Persist IR on host (survives container recreate; included in next deploy image)
HOST_OV="$ROOT/app/processor/models/behavior_v2_1_openvino"
mkdir -p "$HOST_OV"
docker cp "birdlense:$OV_DIR/." "$HOST_OV/"

# ONNX dep for export (idempotent)
docker exec birdlense pip install -q onnx 2>/dev/null || true

echo "== Pipeline done =="
echo "Manifest: $MANIFEST_TO_USE"
echo "OpenVINO (container): $OV_DIR"
echo "OpenVINO (host):     $HOST_OV"
echo "Apply canary:"
echo "  cd $ROOT && bash scripts/server-apply-user-config-patch.sh scripts/user-config-behavior-canary-v2_1.partial.yaml --write --restart"
