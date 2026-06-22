#!/usr/bin/env bash
set -euo pipefail

detector_onnx="${BIRDLENSE_DETECTOR_ONNX:-app/processor/models/detection/weights/yolo11n.onnx}"
out_engine="${BIRDLENSE_DETECTOR_ENGINE:-app/processor/models/detection/weights/yolo11n.engine}"
workspace="${TRT_WORKSPACE_MB:-512}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --detector) detector_onnx="$2"; shift 2 ;;
    --output) out_engine="$2"; shift 2 ;;
    --workspace-mb) workspace="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ ! -f "$detector_onnx" ]; then
  echo "ERROR: detector ONNX missing: $detector_onnx" >&2
  echo "Ornimetrics HF currently publishes model_feeder4.hef, not model_feeder4.onnx; export YOLOv11n ONNX first." >&2
  exit 2
fi
if ! command -v trtexec >/dev/null 2>&1; then
  echo "ERROR: trtexec missing. Install JetPack TensorRT tooling/native DeepStream on Jetson." >&2
  exit 3
fi

mkdir -p "$(dirname "$out_engine")"
trtexec \
  --onnx="$detector_onnx" \
  --saveEngine="$out_engine" \
  --fp16 \
  --workspace="$workspace"

sha256sum "$detector_onnx" "$out_engine" > "${out_engine}.sha256"
echo "TensorRT detector engine written to $out_engine"
