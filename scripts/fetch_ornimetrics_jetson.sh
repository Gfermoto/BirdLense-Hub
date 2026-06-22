#!/usr/bin/env bash
# Ornimetrics edge pack → Jetson layout (reid + welfare only; species classifiers removed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${1:-$ROOT/app/processor/models}"

REID="$BASE/reid/ornimetrics"
WELF="$BASE/welfare/ornimetrics"
mkdir -p "$REID" "$WELF"

if ! python3 -c "import huggingface_hub" 2>/dev/null; then
  python3 -m pip install --user --quiet "huggingface_hub>=0.23,<1"
fi

python3 - "$BASE" <<'PY'
import shutil
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

base = Path(sys.argv[1])
reid_dir = base / "reid" / "ornimetrics"
welf_dir = base / "welfare" / "ornimetrics"

snapshot = Path(
    snapshot_download(
        "Ornimetrics/ornimetrics-edge",
        revision="main",
        allow_patterns=["models/*"],
        ignore_patterns=["*.hef"],
    )
)
src = snapshot / "models"
mapping = {
    "reid_embedder.onnx": reid_dir,
    "embedder.onnx": welf_dir,
    "welfare_scorer.npz": welf_dir,
}
for name, dest in mapping.items():
    s = src / name
    if not s.is_file():
        raise SystemExit(f"Missing Ornimetrics file: {name}")
    shutil.copy2(s, dest / name)

print("Synced Ornimetrics reid+welfare to", base)
PY

echo "ReID:    $REID"
echo "Welfare: $WELF"
