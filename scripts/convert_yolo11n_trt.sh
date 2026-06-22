#!/usr/bin/env bash
set -euo pipefail

# Jetson Nano: YOLOv11n PT/ONNX → TensorRT .engine
# Requires: NVIDIA Container Toolkit, trtexec in path (JetPack), yolo11n.pt

PT_WEIGHTS="${1:-app/processor/models/detection/weights/yolo11n.pt}"
ONNX_OUT="${2:-app/processor/models/detection/weights/yolo11n.onnx}"
ENGINE_OUT="${3:-app/processor/models/detection/weights/yolo11n.engine}"
IMGSZ="${YOLO11N_IMGSZ:-416}"

if [ ! -f "$PT_WEIGHTS" ]; then
  echo "ERROR: yolo11n.pt not found at $PT_WEIGHTS" >&2
  echo "Run: curl -fsSL -o $PT_WEIGHTS https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt" >&2
  exit 2
fi

# Export PT → ONNX (if onnx not exists)
if [ ! -f "$ONNX_OUT" ]; then
  echo "Exporting yolo11n.pt → yolo11n.onnx (imgsz=$IMGSZ)..."
  python3 - <<PY
from pathlib import Path
from ultralytics import YOLO
weights = Path("$PT_WEIGHTS")
out = Path("$ONNX_OUT")
model = YOLO(str(weights), task="detect")
exported = Path(model.export(format="onnx", imgsz=int("$IMGSZ"), simplify=True, opset=12, dynamic=False))
out.parent.mkdir(parents=True, exist_ok=True)
if exported.resolve() != out.resolve():
    out.write_bytes(exported.read_bytes())
print("ONNX export complete:", out)
PY
fi

# ONNX → TensorRT .engine (Jetson)
if command -v trtexec >/dev/null 2>&1; then
  echo "Converting ONNX → TensorRT engine (FP16)..."
  trtexec --onnx="$ONNX_OUT" --saveEngine="$ENGINE_OUT" --fp16 --workspace=512 --verbose 2>&1 | tail -20
  echo "✓ TensorRT engine ready: $ENGINE_OUT"
else
  echo "WARNING: trtexec not found. Install TensorRT tools or run inside NVIDIA container." >&2
  echo "After download, engine build: trtexec --onnx=$ONNX_OUT --saveEngine=$ENGINE_OUT --fp16"
fi

ls -la "$(dirname "$ENGINE_OUT")/"
