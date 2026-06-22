#!/usr/bin/env bash
# Jetson: Trapper ONNX → FP16 engine (flat layout), then start Hub.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="/usr/src/tensorrt/bin:$PATH"
export TRAPPER_IMGSZ="${TRAPPER_IMGSZ:-704}"
export TRTEXEC_WORKSPACE_MB="${TRTEXEC_WORKSPACE_MB:-256}"
export JETSON_TRT_PREFLIGHT=1

TRAPPER_DIR="$ROOT/app/processor/models/detection/trapper_ai_v02_2024"
test -f "$TRAPPER_DIR/trapper_ai_v02_2024.pt"
test -f "$TRAPPER_DIR/trapper_ai_v02_2024.onnx"

if pgrep -x trtexec >/dev/null; then
  echo "trtexec already running — wait for completion or pkill trtexec first" >&2
  exit 2
fi

bash "$ROOT/scripts/export_trapper_detector_trt.sh"
ls -lah "$TRAPPER_DIR/trapper_ai_v02_2024.engine"
sha256sum "$TRAPPER_DIR/trapper_ai_v02_2024.onnx" "$TRAPPER_DIR/trapper_ai_v02_2024.engine" \
  | tee "$TRAPPER_DIR/trapper_ai_v02_2024.engine.sha256"

cd "$ROOT/app"
docker compose -f docker-compose.yml -f docker-compose.jetson.yml up -d --force-recreate birdlense
for i in $(seq 1 40); do
  curl -sf "http://127.0.0.1:${BIRDLENSE_PORT:-8085}/api/ui/health" && exit 0
  sleep 5
done
echo "health check failed" >&2
exit 1
