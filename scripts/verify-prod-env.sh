#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${SCRIPT_DIR}/public/verify-prod-env.sh"
echo "[DEPRECATED] scripts/verify-prod-env.sh -> scripts/public/verify-prod-env.sh" >&2
exec bash "${TARGET}" "$@"
