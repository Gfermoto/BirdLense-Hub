#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${SCRIPT_DIR}/public/restore-config.sh"
echo "[DEPRECATED] scripts/restore-config.sh -> scripts/public/restore-config.sh" >&2
exec bash "${TARGET}" "$@"
