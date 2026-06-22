#!/usr/bin/env bash
set -euo pipefail

weights="${1:-app/processor/models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.pt}"
out="${2:-app/processor/models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.onnx}"
imgsz="${TRAPPER_IMGSZ:-704}"

if [ ! -f "$weights" ]; then
  echo "ERROR: TrapperAI weights missing: $weights" >&2
  echo "Download OSCF/TrapperAI-v02.2024 best.pt into app/processor/models/detection/trapper_ai_v02_2024/." >&2
  exit 2
fi

python3 - <<PY
from pathlib import Path
from ultralytics import YOLO

weights = Path("$weights")
out = Path("$out")
model = YOLO(str(weights), task="detect")
exported = Path(model.export(format="onnx", imgsz=int("$imgsz"), simplify=True, opset=12, dynamic=False))
out.parent.mkdir(parents=True, exist_ok=True)
if exported.resolve() != out.resolve():
    out.write_bytes(exported.read_bytes())
print(out)
PY
