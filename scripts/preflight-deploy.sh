#!/usr/bin/env bash
# Orin/prod deploy preflight: secrets, MCP token, strict API auth, processor config drift.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f scripts/deploy.local.sh ]]; then
  # shellcheck disable=SC1091
  set -a
  # shellcheck source=/dev/null
  . scripts/deploy.local.sh
  set +a
fi

fail=0
note() { echo "preflight-deploy: $*"; }
die() { note "FAIL: $*"; fail=1; }

env_name="${BIRDLENSE_ENV:-}"
if [[ -z "$env_name" && -f app/.env ]]; then
  env_name="$(grep -E '^BIRDLENSE_ENV=' app/.env | head -1 | cut -d= -f2- | tr -d '"'"'" || true)"
fi
env_name="$(echo "${env_name:-}" | tr '[:upper:]' '[:lower:]')"
is_prod=0
if [[ "$env_name" == "production" || "$env_name" == "prod" ]]; then
  is_prod=1
fi
# Orin LAN deploy is treated as production for gate purposes when DEPLOY_HOST set.
if [[ -n "${DEPLOY_HOST:-}" ]]; then
  is_prod=1
fi

require_nonempty() {
  local name="$1"
  local val="${!name:-}"
  if [[ -z "$val" ]]; then
    die "$name must be set for deploy preflight"
  fi
}

if [[ "$is_prod" -eq 1 ]]; then
  note "production/orin path: enforcing secrets + auth gates"
  require_nonempty FLASK_SECRET_KEY
  require_nonempty PROCESSOR_SECRET
  require_nonempty MCP_TOKEN
  if [[ "${BIRDLENSE_STRICT_API_AUTH:-}" != "1" ]]; then
    die "BIRDLENSE_STRICT_API_AUTH=1 required for production/orin deploy"
  fi
  # length sanity without printing values
  if [[ ${#FLASK_SECRET_KEY} -lt 16 ]]; then
    die "FLASK_SECRET_KEY looks too short"
  fi
  if [[ ${#PROCESSOR_SECRET} -lt 16 ]]; then
    die "PROCESSOR_SECRET looks too short"
  fi
  if [[ ${#MCP_TOKEN} -lt 16 ]]; then
    die "MCP_TOKEN looks too short"
  fi
else
  note "non-production: secrets optional; still checking config drift"
fi

if [[ -f scripts/verify_processor_config_drift.py ]]; then
  note "running processor config drift check"
  if ! python3 scripts/verify_processor_config_drift.py; then
    die "processor config drift critical"
  fi
fi

if [[ "$fail" -ne 0 ]]; then
  note "FAILED"
  exit 1
fi
note "PASS"
exit 0
