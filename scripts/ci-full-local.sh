#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${SCRIPT_DIR}/public/ci-full-local.sh"
echo "[DEPRECATED] scripts/ci-full-local.sh -> scripts/public/ci-full-local.sh" >&2
exec bash "${TARGET}" "$@"
