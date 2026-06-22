#!/usr/bin/env bash
# После docker compose --force-recreate на Jetson: hotfix до пересборки образа.
set -euo pipefail
APP_DIR="${1:-/home/gfer/BirdLense/app}"
CONTAINER="${BIRDLENSE_CONTAINER:-birdlense}"

docker cp "$APP_DIR/processor/src/main.py" "$CONTAINER:/app/processor/src/main.py"
docker cp "$APP_DIR/processor/src/inference/selector.py" "$CONTAINER:/app/processor/src/inference/selector.py"
docker cp "$APP_DIR/processor/src/inference/efficientnet_b2_classifier.py" \
  "$CONTAINER:/app/processor/src/inference/efficientnet_b2_classifier.py"
docker cp "$APP_DIR/processor/src/inference/binary_paths.py" \
  "$CONTAINER:/app/processor/src/inference/binary_paths.py"

docker exec "$CONTAINER" pip3 install --no-cache-dir \
  'ultralytics>=8.4,<9' \
  'transformers>=4.40,<5' \
  'huggingface-hub>=0.23,<1' \
  'safetensors>=0.4,<1' \
  'scikit-learn>=1.3,<2'

echo "jetson post-recreate bootstrap: OK ($CONTAINER)"
