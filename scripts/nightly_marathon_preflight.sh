#!/usr/bin/env bash
# Pre-flight for nightly marathon: snapshot, DB backup, disk check.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${ROOT}/logs/nightly_marathon"
mkdir -p "$OUT_DIR"
SNAP="${OUT_DIR}/preflight_${STAMP}.json"
DB="${DB_PATH:-app/data/db/birdlense.db}"
if [[ -f "${ROOT}/app/data/db/birdlense.db" ]]; then
  DB="${ROOT}/app/data/db/birdlense.db"
elif [[ -f /app/data/db/birdlense.db ]]; then
  DB="/app/data/db/birdlense.db"
fi

python3 - <<'PY' "$SNAP" "$DB"
import json, sqlite3, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

snap_path = Path(sys.argv[1])
db_path = Path(sys.argv[2])

def disk():
    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=15)
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        return lines[-1] if lines else None
    except Exception as e:
        return str(e)

def mem():
    try:
        r = subprocess.run(
            ["docker", "stats", "birdlense", "--no-stream", "--format", "{{.MemUsage}}|{{.MemPerc}}"],
            capture_output=True, text=True, timeout=20,
        )
        return (r.stdout or "").strip()
    except Exception:
        return None

baseline = {"at": datetime.now(timezone.utc).isoformat(), "disk_root": disk(), "docker_mem": mem()}
if db_path.is_file():
    con = sqlite3.connect(str(db_path))
    baseline["total_videos"] = con.execute("SELECT COUNT(*) FROM video WHERE deleted_at IS NULL").fetchone()[0]
    both = con.execute(
        """SELECT COUNT(*) FROM video WHERE deleted_at IS NULL
        AND behavior_label IS NOT NULL AND behavior_shadow_label IS NOT NULL"""
    ).fetchone()[0]
    disc = con.execute(
        """SELECT COUNT(*) FROM video WHERE deleted_at IS NULL
        AND behavior_label IS NOT NULL AND behavior_shadow_label IS NOT NULL
        AND LOWER(behavior_label) != LOWER(behavior_shadow_label)"""
    ).fetchone()[0]
    baseline["discrepancy_rate"] = round(disc / both, 4) if both else None
    baseline["al_pending"] = con.execute(
        "SELECT COUNT(*) FROM active_learning_case WHERE status='pending'"
    ).fetchone()[0]
    con.close()
else:
    baseline["db_error"] = "not found"

snap_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
print(json.dumps({"ok": True, "snapshot": str(snap_path), **baseline}, ensure_ascii=False))
PY

if [[ -f "$DB" ]]; then
  BAK="${OUT_DIR}/birdlense_${STAMP}.db.bak"
  cp -a "$DB" "$BAK"
  echo "DB backup: $BAK"
fi

echo "Pre-flight complete. Snapshot: $SNAP"
