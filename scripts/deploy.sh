#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${SCRIPT_DIR}/public/deploy.sh"
echo "[DEPRECATED] scripts/deploy.sh -> scripts/public/deploy.sh" >&2
exec bash "${TARGET}" "$@"
