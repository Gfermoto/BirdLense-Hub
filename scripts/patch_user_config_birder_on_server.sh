#!/usr/bin/env bash
# Set birder_eu classifier on remote user_config (not rsynced by deploy).
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
p = Path("app/app_config/user_config.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
proc = data.setdefault("processor", {})
proc["classifier_engine"] = "birder_eu"
proc["birder_eu_variant"] = "convnext_v2_tiny_eu-common256px"
proc["birder_eu_min_confidence"] = 0.22
models = proc.setdefault("models", {})
models["classifier_birder_eu"] = "models/classification/weights/birder_convnext_v2_tiny_eu_common256px"
models["classifier_birder_eu_openvino"] = (
    "models/classification/weights/birder_convnext_v2_tiny_eu_common256px_openvino"
)
species = data.setdefault("species", {})
species["catalog_allowlist_file"] = (
    "models/classification/weights/birder_convnext_v2_tiny_eu_common256px/class_labels.txt"
)
p.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("patched", p, "classifier_engine=", proc.get("classifier_engine"))
PY
