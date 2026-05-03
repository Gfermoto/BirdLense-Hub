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
# Run API compare from the hub host itself. Public domain may be unreachable
# from inside some VPS networking setups, so localhost is the safe default.
BASE_URL="${BASE_URL:-${DEPLOY_INTERNAL_URL:-http://127.0.0.1:8085}}"
API_KEY="${BIRDLENSE_UI_API_KEY:-}"
MCP_TOKEN_VAL="${MCP_TOKEN:-}"

DAYS="${DAYS:-14}"
MIN_YOLO_SHARE="${MIN_YOLO_SHARE:-0.30}"
MIN_YOLO_SHARE_BIRD_ONLY="${MIN_YOLO_SHARE_BIRD_ONLY:-0.30}"
MIN_YOLO_SHARE_BIRD_ONLY_WARN="${MIN_YOLO_SHARE_BIRD_ONLY_WARN:-0.15}"
MIN_YOLO_TRACK_FOUND_RATE_WARN="${MIN_YOLO_TRACK_FOUND_RATE_WARN:-0.40}"
MIN_DECISION_TRACE_ROWS_WARN="${MIN_DECISION_TRACE_ROWS_WARN:-20}"
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
    --mcp-token '${MCP_TOKEN_VAL}' \
    --api-timeout-seconds '${API_TIMEOUT_SECONDS}' \
    --min-yolo-share '${MIN_YOLO_SHARE}' \
    --min-yolo-share-bird-only '${MIN_YOLO_SHARE_BIRD_ONLY}' \
    --min-yolo-share-bird-only-warn '${MIN_YOLO_SHARE_BIRD_ONLY_WARN}' \
    --min-yolo-track-found-rate-warn '${MIN_YOLO_TRACK_FOUND_RATE_WARN}' \
    --min-decision-trace-rows-warn '${MIN_DECISION_TRACE_ROWS_WARN}' \
    --max-duplicate-video-groups '${MAX_DUPLICATE_VIDEO_GROUPS}' \
    --max-duplicate-detection-groups '${MAX_DUPLICATE_DETECTION_GROUPS}' \
    --max-generic-overlap-ratio '${MAX_GENERIC_OVERLAP_RATIO}' \
    --max-calendar-delta-ratio '${MAX_CALENDAR_DELTA_RATIO}' \
    --out '${REMOTE_TMP}/fusion_ab_report.v1.json'"

