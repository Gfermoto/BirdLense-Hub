#!/usr/bin/env bash
set -euo pipefail

# Scan full git history for leaked secrets with gitleaks (Docker image).
# Usage:
#   bash scripts/security/scan_git_history_secrets.sh
#   GITLEAKS_REPORT=.artifacts/gitleaks-history.json bash scripts/security/scan_git_history_secrets.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_PATH="${GITLEAKS_REPORT:-$REPO_ROOT/.artifacts/gitleaks-history.json}"

mkdir -p "$(dirname "$REPORT_PATH")"

echo "[scan] repo: $REPO_ROOT"
echo "[scan] report: $REPORT_PATH"

docker run --rm \
  -v "$REPO_ROOT:/repo" \
  zricethezav/gitleaks:latest \
  git \
  /repo \
  --report-format=json \
  --report-path=/repo/"${REPORT_PATH#"$REPO_ROOT/"}" \
  --redact

echo "[scan] done"
echo "[scan] review findings in: $REPORT_PATH"
