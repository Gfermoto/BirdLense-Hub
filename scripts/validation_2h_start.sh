#!/usr/bin/env bash
# Start 2h validation monitor on VPS (Canary / Blind / Monitor fixes).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VAL_DIR="${ROOT}/app/data/nightly_marathon/validation_2h"
mkdir -p "$VAL_DIR/crops" "${ROOT}/docs/reports"
METRICS="${VAL_DIR}/validation_2h_${STAMP}.json"
LOG="${VAL_DIR}/validation_2h_${STAMP}.log"
PIDFILE="${VAL_DIR}/validation_2h.pid"
BASELINE="${VAL_DIR}/baseline_${STAMP}.json"
CONTAINER="${MARATHON_CONTAINER:-birdlense}"

# Hot-copy into container
for f in behavior_video_runtime.py recording_finalize.py; do
  docker cp "${ROOT}/app/processor/src/${f}" "${CONTAINER}:/app/processor/src/${f}"
done
docker cp "${ROOT}/app/shared/behavior_tracklet_crop.py" "${CONTAINER}:/app/shared/behavior_tracklet_crop.py"
for f in monitor_long_run.py ml_behavior_harvest_nightly.py ml_behavior_crop_core.py; do
  docker cp "${ROOT}/scripts/${f}" "${CONTAINER}:/app/scripts/${f}" 2>/dev/null || true
done

echo "=== restart birdlense ===" | tee -a "$LOG"
cd "${ROOT}/app" && docker compose restart birdlense
sleep 20
docker ps --filter name=birdlense --format "{{.Names}} {{.Status}}" | tee -a "$LOG"
docker logs "${CONTAINER}" --tail 30 2>&1 | grep -iE "behavior|openvino|error|behavior_video" | tail -15 | tee -a "$LOG" || true

python3 - <<PY "$BASELINE"
import json, sqlite3, subprocess
from datetime import datetime, timezone
from pathlib import Path

baseline_path = Path(__import__("sys").argv[1])
db = Path("$ROOT/app/data/db/birdlense.db")
if not db.is_file():
    db = Path("/app/data/db/birdlense.db")
out = {"started_at": datetime.now(timezone.utc).isoformat(), "stamp": "$STAMP"}
if db.is_file():
    con = sqlite3.connect(str(db))
    out["total_videos"] = con.execute("SELECT COUNT(*) FROM video WHERE deleted_at IS NULL").fetchone()[0]
    out["with_shadow"] = con.execute(
        "SELECT COUNT(*) FROM video WHERE deleted_at IS NULL AND behavior_shadow_label IS NOT NULL"
    ).fetchone()[0]
    con.close()
try:
    r = subprocess.run(
        ["docker", "exec", "$CONTAINER", "test", "-f", "/app/processor/models/behavior_v2_openvino/behavior_video_model.xml"],
        capture_output=True,
    )
    out["behavior_v2_xml"] = r.returncode == 0
except Exception as e:
    out["behavior_v2_xml_error"] = str(e)
baseline_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False))
PY

export PYTHONPATH="${ROOT}/scripts:${PYTHONPATH:-}"
export HARVEST_DOCKER_CONTAINER="${CONTAINER}"
nohup python3 "${ROOT}/scripts/monitor_long_run.py" \
  --duration 2h \
  --interval 15m \
  --output "$METRICS" \
  --report "${VAL_DIR}/validation_2h_${STAMP}.md" \
  --db "${ROOT}/app/data/db/birdlense.db" \
  --crops-dir "${VAL_DIR}/crops" \
  --repo-root "${ROOT}/app" \
  --focus-class flying \
  --harvest-every 1 \
  --harvest-docker "${CONTAINER}" \
  >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"

echo "VALIDATION_STARTED stamp=$STAMP pid=$(cat $PIDFILE)" | tee -a "$LOG"
echo "metrics=$METRICS"
echo "log=$LOG"
echo "baseline=$BASELINE"
