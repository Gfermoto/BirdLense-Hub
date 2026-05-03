#!/usr/bin/env bash
# Build fusion_ab_report@v1 on deployed hub SQLite (+ optional API compare).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "${SCRIPT_DIR}/deploy.local.sh" ]; then
  # shellcheck disable=SC1091
  . "${SCRIPT_DIR}/deploy.local.sh"
fi

HOST="${DEPLOY_HOST:-birdlense}"
PORT="${DEPLOY_SSH_PORT:-22}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
REMOTE_TMP="${REMOTE_TMP:-/tmp/bl_metrics}"
DB_PATH="${DB_PATH:-${REMOTE_DIR}/app/data/db/birdlense.db}"
BASE_URL="${DEPLOY_URL:-}"
API_KEY="${BIRDLENSE_UI_API_KEY:-}"

DAYS="${DAYS:-14}"
MIN_YOLO_SHARE="${MIN_YOLO_SHARE:-0.30}"
MAX_DUPLICATE_VIDEO_GROUPS="${MAX_DUPLICATE_VIDEO_GROUPS:-0}"
MAX_DUPLICATE_DETECTION_GROUPS="${MAX_DUPLICATE_DETECTION_GROUPS:-0}"
MAX_GENERIC_OVERLAP_RATIO="${MAX_GENERIC_OVERLAP_RATIO:-0.60}"
MAX_CALENDAR_DELTA_RATIO="${MAX_CALENDAR_DELTA_RATIO:-5.00}"
API_TIMEOUT_SECONDS="${API_TIMEOUT_SECONDS:-8.0}"

SSH_OPTS=(-p "${PORT}" -o ServerAliveInterval=30 -o ServerAliveCountMax=20)

echo "ml-fusion-ab-hub: host=${HOST} db=${DB_PATH} tmp=${REMOTE_TMP}"
ssh "${SSH_OPTS[@]}" "${HOST}" "mkdir -p '${REMOTE_TMP}'"

ssh "${SSH_OPTS[@]}" "${HOST}" \
  "python3 '${REMOTE_DIR}/scripts/ml_fusion_ab_report.py' \
    --db '${DB_PATH}' \
    --days '${DAYS}' \
    --base-url '${BASE_URL}' \
    --api-key '${API_KEY}' \
    --api-timeout-seconds '${API_TIMEOUT_SECONDS}' \
    --min-yolo-share '${MIN_YOLO_SHARE}' \
    --max-duplicate-video-groups '${MAX_DUPLICATE_VIDEO_GROUPS}' \
    --max-duplicate-detection-groups '${MAX_DUPLICATE_DETECTION_GROUPS}' \
    --max-generic-overlap-ratio '${MAX_GENERIC_OVERLAP_RATIO}' \
    --max-calendar-delta-ratio '${MAX_CALENDAR_DELTA_RATIO}' \
    --out '${REMOTE_TMP}/fusion_ab_report.v1.json'"

