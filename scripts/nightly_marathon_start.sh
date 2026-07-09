#!/usr/bin/env bash
# Start 8h nightly marathon monitor (survives SSH disconnect).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date -u +%Y%m%d)"
CONTAINER="${MARATHON_CONTAINER:-birdlense}"
DATA_MARATHON="${ROOT}/app/data/nightly_marathon"
mkdir -p "$DATA_MARATHON/crops" "${ROOT}/docs/reports"
METRICS="${DATA_MARATHON}/nightly_marathon_${STAMP}.json"
REPORT="${DATA_MARATHON}/nightly_marathon_${STAMP}.md"
REPORT_DOCS="${ROOT}/docs/reports/nightly_marathon_${STAMP}.md"
LOG="${DATA_MARATHON}/nightly_marathon_${STAMP}.log"
PIDFILE="${DATA_MARATHON}/marathon.pid"

DB_HOST="${ROOT}/app/data/db/birdlense.db"

bash "${ROOT}/scripts/nightly_marathon_preflight.sh" | tee -a "$LOG"

for f in monitor_long_run.py ml_behavior_harvest_nightly.py; do
  docker cp "${ROOT}/scripts/${f}" "${CONTAINER}:/app/scripts/${f}"
done

echo "processor_log_anchor_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
docker logs "${CONTAINER}" --tail 3 >>"$LOG" 2>&1 || true

export PYTHONPATH="${ROOT}/scripts:${PYTHONPATH:-}"
export HARVEST_DOCKER_CONTAINER="${CONTAINER}"
nohup python3 "${ROOT}/scripts/monitor_long_run.py" \
  --duration "${DURATION:-8h}" \
  --interval "${INTERVAL:-30m}" \
  --output "$METRICS" \
  --report "$REPORT" \
  --db "$DB_HOST" \
  --crops-dir "${DATA_MARATHON}/crops" \
  --repo-root "${ROOT}/app" \
  --focus-class flying \
  --harvest-every 2 \
  --harvest-docker "${CONTAINER}" \
  >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
echo "Started marathon host PID=$(cat "$PIDFILE") harvest_via=${CONTAINER}"
echo "Log: $LOG"
echo "Metrics: $METRICS"
echo "Report (on finish): $REPORT"
ln -sf "$REPORT" "$REPORT_DOCS" 2>/dev/null || true
