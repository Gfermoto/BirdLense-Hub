#!/usr/bin/env bash
# Birder EU classifier paths on remote user_config.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"
HOST="${DEPLOY_HOST:?}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
_PORT_OPT=""
[ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ] && _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
SSH_OPTS="${_PORT_OPT} -o BatchMode=yes -o ConnectTimeout=20"

ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}' && python3 -" <<'PY'
from pathlib import Path
import yaml

variant = "convnext_v2_tiny_eu-common256px"
p = Path("app/app_config/user_config.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
proc = data.setdefault("processor", {})
proc["classifier_engine"] = "birder_eu"
proc["birder_eu_variant"] = variant
proc["classifier_inference_backend"] = "onnxruntime"
models = proc.setdefault("models", {})
models["classifier"] = f"models/classification/{variant}/{variant}.onnx"
for k in (
    "classifier_openvino",
    "classifier_birder_eu",
    "classifier_birder_eu_openvino",
    "classifier_yolo_legacy",
    "classifier_efficientnet_b2",
):
    models.pop(k, None)
species = data.setdefault("species", {})
species["catalog_allowlist_file"] = f"models/classification/{variant}/class_labels.txt"
p.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("patched", p)
PY
