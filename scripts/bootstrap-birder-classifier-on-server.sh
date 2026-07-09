#!/usr/bin/env bash
# Download Birder EU classifier + ONNX export on remote hub (after code deploy).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=/dev/null
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:?Set DEPLOY_HOST in scripts/deploy.local.sh}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=120 -o BatchMode=yes -o ConnectTimeout=20"

echo "=== Birder EU weights on ${HOST} ==="
ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}' && bash -s" <<'REMOTE'
set -euo pipefail
cd /root/BirdLense
if ! python3 -c "import birder" 2>/dev/null; then
  pip3 install -q birder huggingface_hub torch torchvision 2>/dev/null || \
    python3 -m pip install -q birder huggingface_hub torch torchvision
fi
python3 scripts/download_birder_classifier.py --variant convnext_v2_tiny_eu-common256px --export-onnx
ls -la app/processor/models/classification/convnext_v2_tiny_eu-common256px/convnext_v2_tiny_eu-common256px.onnx
ls -la app/processor/models/classification/convnext_v2_tiny_eu-common256px/class_labels.txt
REMOTE
echo "OK Birder weights on server"
