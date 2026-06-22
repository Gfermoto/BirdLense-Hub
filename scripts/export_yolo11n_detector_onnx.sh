#!/usr/bin/env bash
set -euo pipefail

weights="${1:-app/processor/models/detection/weights/yolo11n.pt}"
out="${2:-app/processor/models/detection/weights/yolo11n.onnx}"
imgsz="${YOLO11N_IMGSZ:-416}"

if [ ! -f "$weights" ]; then
  echo "ERROR: YOLO source weights missing: $weights" >&2
  echo "Provide yolo11n.pt or a project-trained YOLOv11n .pt; do not use Ornimetrics .hef on Jetson." >&2
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
