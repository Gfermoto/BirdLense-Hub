#!/usr/bin/env bash
# Prod pipeline health gate (#592): session_runtime_metrics SLO from #591.
# Fetch prod DB snapshot (optional), run outcome + runtime profile gates.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

FETCH_PROD="${PIPELINE_HEALTH_FETCH_PROD:-1}"
DB_PATH="${PIPELINE_HEALTH_DB_PATH:-app/data/db/birdlense_prod_latest.db}"
LOOKBACK_H="${PIPELINE_HEALTH_LOOKBACK_HOURS:-24}"
DATA_SOURCE="${PIPELINE_HEALTH_DATA_SOURCE:-prod:session_runtime_metrics}"

# Interim thresholds while track-density tuning is in flight (target DoD: 0.50).
MIN_TRACKS_COVERAGE="${PIPELINE_HEALTH_MIN_TRACKS_COVERAGE:-0.20}"
MAX_EMPTY_BBOX_RATE="${PIPELINE_HEALTH_MAX_EMPTY_BBOX_RATE:-0.35}"
MAX_BLIND_RATE="${PIPELINE_HEALTH_MAX_BLIND_RATE:-0.40}"
MIN_YOLO_FRAMES_WITH_TRACKS="${PIPELINE_HEALTH_MIN_YOLO_FRAMES_WITH_TRACKS:-1}"
FIRST_BBOX_WARN_S="${PIPELINE_HEALTH_FIRST_BBOX_WARN_S:-8}"
FINALIZE_WARN_MS="${PIPELINE_HEALTH_FINALIZE_WARN_MS:-8000}"
PERSIST_WARN_MS="${PIPELINE_HEALTH_PERSIST_WARN_MS:-6000}"

if [[ "${FETCH_PROD}" == "1" ]]; then
  echo "pipeline-health-gate: fetching prod DB snapshot..."
  "${SCRIPT_DIR}/fetch_prod_db_snapshot.sh"
fi

if [[ ! -f "${DB_PATH}" ]]; then
  echo "pipeline-health-gate: DB not found: ${DB_PATH}" >&2
  exit 2
fi

echo "pipeline-health-gate: outcome metrics (lookback=${LOOKBACK_H}h, db=${DB_PATH})"
python3 ./scripts/report_quality_outcome_metrics.py \
  --db-path "${DB_PATH}" \
  --data-source "${DATA_SOURCE}" \
  --lookback-hours "${LOOKBACK_H}" \
  --max-blind-rate "${MAX_BLIND_RATE}" \
  --min-tracks-coverage "${MIN_TRACKS_COVERAGE}" \
  --max-empty-bbox-rate "${MAX_EMPTY_BBOX_RATE}" \
  --min-yolo-frames-with-tracks "${MIN_YOLO_FRAMES_WITH_TRACKS}" \
  --max-ingest-pruned-rows-per-hour-delta-vs-7d "${PIPELINE_HEALTH_MAX_INGEST_PRUNED_DELTA:-0.5}" \
  --max-frigate-catches-missed-birds-rate "${PIPELINE_HEALTH_MAX_FRIGATE_MISS_RATE:-0.05}" \
  --max-frigate-catches-missed-birds-rate-delta-vs-7d "${PIPELINE_HEALTH_MAX_FRIGATE_MISS_DELTA:-0.05}"

echo "pipeline-health-gate: runtime pipeline profile"
OUTCOME_DB_PATH="${DB_PATH}" \
OUTCOME_LOOKBACK_HOURS="${LOOKBACK_H}" \
FIRST_BBOX_WARN_S="${FIRST_BBOX_WARN_S}" \
FINALIZE_WARN_MS="${FINALIZE_WARN_MS}" \
PERSIST_WARN_MS="${PERSIST_WARN_MS}" \
  make runtime-pipeline-profile

echo "pipeline-health-gate: OK"
