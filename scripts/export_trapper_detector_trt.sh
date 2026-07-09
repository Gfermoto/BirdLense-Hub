#!/usr/bin/env bash
# Jetson Nano: TrapperAI PT → ONNX → TensorRT .engine
# Safe defaults for 4GB Nano: imgsz=704 (set TRAPPER_IMGSZ=1024 if headroom), stop Hub before build.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TRAPPER_DIR="${TRAPPER_DIR:-$ROOT/app/processor/models/detection/trapper_ai_v02_2024}"
PT="${1:-$TRAPPER_DIR/trapper_ai_v02_2024.pt}"
ONNX="${2:-$TRAPPER_DIR/trapper_ai_v02_2024.onnx}"
ENGINE="${3:-$TRAPPER_DIR/trapper_ai_v02_2024.engine}"
IMGSZ="${TRAPPER_IMGSZ:-704}"
WORKSPACE_MB="${TRTEXEC_WORKSPACE_MB:-256}"  # 512 @1024 often OOM-reboot on 4GB Nano

if [[ ! -f "$PT" ]]; then
  echo "ERROR: missing $PT" >&2
  exit 2
fi

if [[ "${JETSON_TRT_PREFLIGHT:-1}" == "1" ]]; then
  echo "Preflight: stop birdlense before trtexec on 4GB Nano (export JETSON_TRT_PREFLIGHT=0 to skip)."
  if command -v docker >/dev/null 2>&1; then
    docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^birdlense$' && {
      echo "Stopping birdlense container to free GPU/RAM..."
      docker stop birdlense || true
    }
  fi
  free -h || true
fi

if [[ ! -f "$ONNX" ]]; then
  echo "Exporting trapper → ONNX (imgsz=$IMGSZ)..."
  python3 - <<PY
from pathlib import Path
from ultralytics import YOLO
weights = Path("$PT")
out = Path("$ONNX")
model = YOLO(str(weights), task="detect")
exported = Path(model.export(format="onnx", imgsz=int("$IMGSZ"), simplify=True, opset=12, dynamic=False))
out.parent.mkdir(parents=True, exist_ok=True)
if exported.resolve() != out.resolve():
    out.write_bytes(exported.read_bytes())
print("names:", model.names)
print("ONNX:", out)
PY
fi

export PATH="/usr/src/tensorrt/bin:$PATH"
if command -v trtexec >/dev/null 2>&1; then
  TRTEXEC=trtexec
elif [ -x /usr/src/tensorrt/bin/trtexec ]; then
  TRTEXEC=/usr/src/tensorrt/bin/trtexec
else
  echo "WARNING: trtexec not found" >&2
  exit 3
fi

echo "trtexec FP16 workspace=${WORKSPACE_MB}MB imgsz=${IMGSZ} (704 safe on 4GB Nano; TRAPPER_IMGSZ=1024 if headroom)..."
"$TRTEXEC" \
  --onnx="$ONNX" \
  --saveEngine="$ENGINE" \
  --fp16 \
  --workspace="$WORKSPACE_MB" \
  --verbose 2>&1 | tail -30
echo "✓ engine: $ENGINE"

ls -la "$(dirname "$ENGINE")/"
