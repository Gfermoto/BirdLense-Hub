#!/usr/bin/env bash
# chriamue/bird-species-classifier (525 species, EfficientNet) → Jetson layout.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT/app/processor/models/classification/chriamue_bird_species_classifier}"
REPO_ID="${CHRIAMUE_REPO_ID:-chriamue/bird-species-classifier}"

mkdir -p "$DEST"

if ! python3 -c "import huggingface_hub" 2>/dev/null; then
  python3 -m pip install --user --quiet "huggingface_hub>=0.23,<1"
fi

python3 - "$DEST" "$REPO_ID" <<'PY'
import json
import shutil
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

dest = Path(sys.argv[1])
repo_id = sys.argv[2]

snapshot = Path(
    snapshot_download(
        repo_id,
        allow_patterns=[
            "config.json",
            "preprocessor_config.json",
            "*.safetensors",
            "*.onnx",
            "*.json",
        ],
    )
)

for src in snapshot.rglob("*"):
    if not src.is_file():
        continue
    rel = src.relative_to(snapshot)
    if rel.parts and rel.parts[0] in (".git", ".cache"):
        continue
    out = dest / rel.name
    shutil.copy2(src, out)

cfg_path = dest / "config.json"
if not cfg_path.is_file():
    raise SystemExit(f"Missing config.json in {dest}")

cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
labels = cfg.get("id2label") or {}
print(f"Synced {repo_id} → {dest} ({len(labels)} classes)")
onnx = sorted(dest.glob("*.onnx"))
if onnx:
    print("ONNX:", onnx[0].name)
else:
    print("No ONNX on HF — use classifier_inference_backend=torch or export ONNX separately")
PY

echo "Classifier weights: $DEST"
