#!/usr/bin/env bash
# Ornimetrics ReID + welfare → app/processor/models/{reid,welfare}/ornimetrics/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

bash "${ROOT}/scripts/fetch_ornimetrics.sh" "${TMP}"

REID_DIR="${ROOT}/app/processor/models/reid/ornimetrics"
WELF_DIR="${ROOT}/app/processor/models/welfare/ornimetrics"
mkdir -p "${REID_DIR}" "${WELF_DIR}"

install -m 644 "${TMP}/reid_embedder.onnx" "${REID_DIR}/reid_embedder.onnx"
install -m 644 "${TMP}/embedder.onnx" "${WELF_DIR}/embedder.onnx"
install -m 644 "${TMP}/welfare_scorer.npz" "${WELF_DIR}/welfare_scorer.npz"

echo "OK ${REID_DIR}/reid_embedder.onnx"
echo "OK ${WELF_DIR}/embedder.onnx"
echo "OK ${WELF_DIR}/welfare_scorer.npz"
