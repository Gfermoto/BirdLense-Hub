#!/usr/bin/env bash
# Fetch remote user_config and run processor config drift check (#585 / I2).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
REMOTE_CFG="${REMOTE_DIR}/app/app_config/user_config.yaml"
LOCAL_TMP="${ROOT}/app/app_config/.user_config_prod_drift.yaml"
mkdir -p "${ROOT}/app/app_config"

if [[ -z "${HOST}" ]]; then
  echo "verify-prod-config-drift: DEPLOY_HOST not set" >&2
  exit 2
fi

_SCP_PORT_OPT=()
_SSH_PORT_OPT=()
if [[ -n "${DEPLOY_SSH_PORT:-}" && "${DEPLOY_SSH_PORT}" != "22" ]]; then
  _SCP_PORT_OPT=(-P "${DEPLOY_SSH_PORT}")
  _SSH_PORT_OPT=(-p "${DEPLOY_SSH_PORT}")
fi

echo "verify-prod-config-drift: fetch ${HOST}:${REMOTE_CFG}"
scp "${_SCP_PORT_OPT[@]}" "${HOST}:${REMOTE_CFG}" "${LOCAL_TMP}"

python3 ./scripts/verify_processor_config_drift.py \
  --user-config "${LOCAL_TMP}" \
  --out-json docs/reports/governance/processor_config_drift_prod_latest.json \
  --out-md docs/reports/governance/processor_config_drift_prod_latest.md \
  --fail-on-critical \
  "$@"
