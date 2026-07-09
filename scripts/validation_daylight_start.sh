#!/usr/bin/env bash
# Daylight 2h validation after monitor + blind hotfixes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VAL_DIR="${ROOT}/app/data/nightly_marathon/validation_daylight"
mkdir -p "$VAL_DIR/crops" "${ROOT}/docs/reports"
METRICS="${VAL_DIR}/validation_daylight_${STAMP}.json"
LOG="${VAL_DIR}/validation_daylight_${STAMP}.log"
PIDFILE="${VAL_DIR}/validation_daylight.pid"
CONTAINER="${MARATHON_CONTAINER:-birdlense}"

python3 - <<PY "$VAL_DIR/baseline_${STAMP}.json"
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
p = Path(__import__("sys").argv[1])
db = Path("$ROOT/app/data/db/birdlense.db")
out = {"started_at": datetime.now(timezone.utc).isoformat(), "stamp": "$STAMP"}
if db.is_file():
    con = sqlite3.connect(str(db))
    out["total_videos"] = con.execute("SELECT COUNT(*) FROM video WHERE deleted_at IS NULL").fetchone()[0]
    out["with_shadow"] = con.execute(
        "SELECT COUNT(*) FROM video WHERE deleted_at IS NULL AND behavior_shadow_label IS NOT NULL"
    ).fetchone()[0]
    con.close()
p.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out))
PY

export PYTHONPATH="${ROOT}/scripts:${PYTHONPATH:-}"
export HARVEST_DOCKER_CONTAINER="${CONTAINER}"
nohup python3 "${ROOT}/scripts/monitor_long_run.py" \
  --duration "${DURATION:-2h}" \
  --interval "${INTERVAL:-10m}" \
  --output "$METRICS" \
  --report "${VAL_DIR}/validation_daylight_${STAMP}.md" \
  --db "${ROOT}/app/data/db/birdlense.db" \
  --crops-dir "${VAL_DIR}/crops" \
  --repo-root "${ROOT}/app" \
  --focus-class flying \
  --harvest-every 1 \
  --harvest-docker "${CONTAINER}" \
  >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
echo "DAYLIGHT_VALIDATION_STARTED pid=$(cat $PIDFILE) metrics=$METRICS log=$LOG"
