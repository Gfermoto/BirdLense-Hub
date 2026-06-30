#!/usr/bin/env bash
# Скачать все веса Orin в app/processor/models/ (единственное место хранения).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODELS="${ROOT}/app/processor/models"
TRAPPER_DIR="${MODELS}/detection/trapper_ai_v02_2024"
TRAPPER_ONNX="${TRAPPER_DIR}/trapper_ai_v02_2024.onnx"
TRAPPER_PT="${TRAPPER_DIR}/trapper_ai_v02_2024.pt"
CLF_VARIANT=convnext_v2_tiny_eu-common256px
CLF_DIR="${MODELS}/classification/${CLF_VARIANT}"
CLF_ONNX="${CLF_DIR}/${CLF_VARIANT}.onnx"
REID_ONNX="${MODELS}/reid/ornimetrics/reid_embedder.onnx"
WELF_EMB="${MODELS}/welfare/ornimetrics/embedder.onnx"
WELF_SCORER="${MODELS}/welfare/ornimetrics/welfare_scorer.npz"

echo "=== BirdLense processor models (Orin) ==="

# 1. Trapper detector ONNX
if [[ ! -f "${TRAPPER_ONNX}" ]]; then
  echo "[trapper] ONNX missing — fetch + export"
  if [[ ! -f "${TRAPPER_PT}" ]]; then
    bash "${ROOT}/scripts/fetch_trapper_weights.sh" "${TRAPPER_DIR}"
  fi
  bash "${ROOT}/scripts/export_trapper_detector_onnx.sh" "${TRAPPER_PT}" "${TRAPPER_ONNX}"
else
  echo "[trapper] OK ${TRAPPER_ONNX}"
fi

# 2. Birder EU classifier ONNX
if [[ ! -f "${CLF_ONNX}" ]]; then
  echo "[birder] classifier missing — download + export ONNX"
  if ! python3 -c "import birder" 2>/dev/null; then
    echo "  install: pip install birder huggingface_hub torch" >&2
    exit 2
  fi
  python3 "${ROOT}/scripts/download_birder_classifier.py" --export-onnx
else
  echo "[birder] OK ${CLF_ONNX}"
fi

# 3. Ornimetrics ReID + welfare
if [[ ! -f "${REID_ONNX}" || ! -f "${WELF_EMB}" || ! -f "${WELF_SCORER}" ]]; then
  echo "[ornimetrics] reid/welfare missing — download"
  bash "${ROOT}/scripts/fetch_ornimetrics_orin.sh"
else
  echo "[ornimetrics] OK reid + welfare"
fi

echo "=== Done ==="
find "${MODELS}" -maxdepth 4 -type f \( -name '*.onnx' -o -name '*.npz' -o -name '*.yaml' \) ! -path '*/class_maps/*' | sort
