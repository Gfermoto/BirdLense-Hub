#!/usr/bin/env bash
# OSCF/TrapperAI-v02.2024 → models/detection/trapper_ai_v02_2024/ (.pt для export ONNX).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT/app/processor/models/detection/trapper_ai_v02_2024}"
REPO_ID="${TRAPPER_REPO_ID:-OSCF/TrapperAI-v02.2024}"

mkdir -p "$DEST"

if ! python3 -c "import huggingface_hub" 2>/dev/null; then
  python3 -m pip install --user --quiet "huggingface_hub>=0.23,<1"
fi

python3 - "$DEST" "$REPO_ID" <<'PY'
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

dest = Path(sys.argv[1])
repo_id = sys.argv[2]
dest.mkdir(parents=True, exist_ok=True)

pt_name = "trapper_ai_v02_2024.pt"
try:
    pt = Path(hf_hub_download(repo_id, filename="best.pt", local_dir=dest))
    target = dest / pt_name
    if pt.resolve() != target.resolve():
        shutil.copy2(pt, target)
except Exception:
    snap = Path(snapshot_download(repo_id, allow_patterns=["*.pt", "*.yaml", "*.names"]))
    pts = list(snap.rglob("*.pt"))
    if not pts:
        raise SystemExit(f"No .pt in {repo_id}")
    shutil.copy2(pts[0], dest / pt_name)
    for y in snap.rglob("*.yaml"):
        shutil.copy2(y, dest / "trapper_ai_v02_2024.yaml")
        break

print("Synced", repo_id, "→", dest / pt_name)
PY

# class map next to weights
if [[ -f "$ROOT/app/processor/models/detection/class_maps/trapper_ai_v02_2024.yaml" ]]; then
  cp "$ROOT/app/processor/models/detection/class_maps/trapper_ai_v02_2024.yaml" \
    "$DEST/trapper_ai_v02_2024.yaml"
fi

echo "Trapper weights: $DEST"
