#!/usr/bin/env bash
set -euo pipefail

REPO_ID="${ORNIMETRICS_REPO_ID:-Ornimetrics/ornimetrics-edge}"
REVISION="${ORNIMETRICS_REVISION:-main}"
TARGET="${1:-${ORNIMETRICS_TARGET:-/mnt/ssd/birdlense/models/classification/ornimetrics}}"

mkdir -p "$TARGET"

if ! python3 -c "import huggingface_hub" 2>/dev/null; then
    python3 -m pip install --quiet "huggingface_hub>=0.23,<1"
fi

python3 - "$REPO_ID" "$REVISION" "$TARGET" <<'PY'
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

repo_id, revision, target = sys.argv[1], sys.argv[2], Path(sys.argv[3])
snapshot = Path(
    snapshot_download(
        repo_id,
        revision=revision,
        allow_patterns=[
            "models/*.onnx",
            "models/*.json",
            "models/*.npz",
            "models/*.names",
        ],
        ignore_patterns=["*.hef"],
    )
)

for src in (snapshot / "models").iterdir():
    if src.suffix == ".hef":
        continue
    if src.is_file():
        shutil.copy2(src, target / src.name)

required = {
    "species_classifier_nabirds.onnx",
    "species_classifier_nabirds.json",
    "species_classifier_inat.onnx",
    "embedder.onnx",
    "welfare_scorer.npz",
    "reid_embedder.onnx",
}
inat_json = target / "species_classifier_inat.json"
if not inat_json.is_file():
    print(
        "NOTE: species_classifier_inat.json is not published on HF; generate with "
        "scripts/generate_ornimetrics_inat_json.py once you have the 302-label list.",
        file=sys.stderr,
    )

missing = sorted(name for name in required if not (target / name).is_file())
if missing:
    raise SystemExit(f"Missing Ornimetrics files: {', '.join(missing)}")

if not (target / "model_feeder4.onnx").is_file():
    print(
        "NOTE: Ornimetrics detector ONNX model_feeder4.onnx is not published; "
        "model_feeder4.hef is Hailo-only and was intentionally not downloaded. "
        "Jetson detector: trapper_ai_v02_2024.engine (TensorRT @1024); yolo11n.* is legacy interim.",
        file=sys.stderr,
    )
PY

echo "Ornimetrics ONNX/sidecars synced to $TARGET"
