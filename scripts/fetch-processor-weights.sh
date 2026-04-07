#!/usr/bin/env bash
# Положить two_stage .pt в дерево processor/ (веса в .gitignore — не из git).
# Использование: из корня репозитория: ./scripts/fetch-processor-weights.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DET="${ROOT}/app/processor/models/detection/weights"
CLS="${ROOT}/app/processor/models/classification/weights"
ZIP="${ROOT}/app/processor/models/detection/nabirds_yolo11n_binary.zip"
HF_URL="https://huggingface.co/gfermoto/birdlense-birds-eu/resolve/main/best.pt"

mkdir -p "$DET" "$CLS"

if [[ ! -s "${DET}/best.pt" ]]; then
  echo "Распаковка бинарного детектора из ${ZIP}..."
  unzip -j -o "$ZIP" weights/best.pt -d "$DET/"
else
  echo "Уже есть ${DET}/best.pt — пропуск."
fi

if [[ ! -s "${CLS}/best.pt" ]]; then
  echo "Загрузка EU-классификатора (best.pt)..."
  curl -fsSL -o "${CLS}/best.pt" "$HF_URL"
else
  echo "Уже есть ${CLS}/best.pt — пропуск."
fi

echo "Готово: two_stage ожидает эти пути (или задайте свои в user_config.yaml)."
