#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${SCRIPT_DIR}/public/diagnose.sh"
echo "[DEPRECATED] scripts/diagnose.sh -> scripts/public/diagnose.sh" >&2
exec bash "${TARGET}" "$@"
