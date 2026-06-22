#!/usr/bin/env bash
# После docker compose --force-recreate на Jetson: hotfix исходников processor.
set -euo pipefail
APP_DIR="${1:-/home/gfer/BirdLense/app}"
CONTAINER="${BIRDLENSE_CONTAINER:-birdlense}"

docker cp "$APP_DIR/processor/src/main.py" "$CONTAINER:/app/processor/src/main.py"
docker cp "$APP_DIR/processor/src/detection_strategy.py" "$CONTAINER:/app/processor/src/detection_strategy.py"
docker cp "$APP_DIR/processor/src/inference/trt_ipc_codec.py" \
  "$CONTAINER:/app/processor/src/inference/trt_ipc_codec.py"
docker cp "$APP_DIR/processor/src/inference/__init__.py" \
  "$CONTAINER:/app/processor/src/inference/__init__.py"
docker cp "$APP_DIR/processor/src/inference/selector.py" "$CONTAINER:/app/processor/src/inference/selector.py"
docker cp "$APP_DIR/processor/src/inference/efficientnet_b2_classifier.py" \
  "$CONTAINER:/app/processor/src/inference/efficientnet_b2_classifier.py"
docker cp "$APP_DIR/processor/src/inference/binary_paths.py" \
  "$CONTAINER:/app/processor/src/inference/binary_paths.py"
docker cp "$APP_DIR/processor/src/inference/trt_boxes_shared.py" \
  "$CONTAINER:/app/processor/src/inference/trt_boxes_shared.py"
docker cp "$APP_DIR/processor/src/inference/tensorrt_yolo_detector.py" \
  "$CONTAINER:/app/processor/src/inference/tensorrt_yolo_detector.py"
docker cp "$APP_DIR/processor/src/inference/tensorrt_yolo_client.py" \
  "$CONTAINER:/app/processor/src/inference/tensorrt_yolo_client.py"
docker cp "$APP_DIR/processor/src/inference/jetson_trt_worker.py" \
  "$CONTAINER:/app/processor/src/inference/jetson_trt_worker.py"
docker cp "$APP_DIR/processor/src/inference/jetson_trackers" \
  "$CONTAINER:/app/processor/src/inference/jetson_trackers"
docker cp "$APP_DIR/processor/src/inference/torch_backend.py" \
  "$CONTAINER:/app/processor/src/inference/torch_backend.py"
docker cp "$APP_DIR/processor/src/inference/classifier_paths.py" \
  "$CONTAINER:/app/processor/src/inference/classifier_paths.py"
docker cp "$APP_DIR/scripts/entrypoint.sh" "$CONTAINER:/app/scripts/entrypoint.sh"

if ! docker exec "$CONTAINER" test -x /opt/jetson-processor/bin/python 2>/dev/null; then
  echo "WARN: /opt/jetson-processor missing — rebuild image (make jetson-build) or run install_jetson_processor_venv.sh"
fi

docker exec "$CONTAINER" find /app/processor -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
echo "jetson post-recreate bootstrap: OK ($CONTAINER)"
