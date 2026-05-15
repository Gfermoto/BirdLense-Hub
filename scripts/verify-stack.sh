#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${SCRIPT_DIR}/public/verify-stack.sh"
echo "[DEPRECATED] scripts/verify-stack.sh -> scripts/public/verify-stack.sh" >&2
exec bash "${TARGET}" "$@"
