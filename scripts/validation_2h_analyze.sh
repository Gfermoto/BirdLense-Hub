#!/usr/bin/env bash
# Analyze completed 2h validation JSON + DB.
set -euo pipefail
METRICS="${1:?metrics json path}"
DB="${2:-/root/BirdLense/app/data/db/birdlense.db}"
REPORT="${3:-docs/reports/validation_2h_report.md}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p "$(dirname "$REPORT")"

python3 - <<PY "$METRICS" "$DB" "$REPORT"
import json, sqlite3, subprocess, sys
from pathlib import Path
from collections import Counter

metrics_path = Path(sys.argv[1])
db_path = Path(sys.argv[2])
report_path = Path(sys.argv[3])

d = json.loads(metrics_path.read_text())
started = d.get("started_at", "")
ended = d.get("ended_at", started)
samples = d.get("samples") or []

# YOLO from probes
sess_total = sum(int((s.get("yolo") or {}).get("sessions") or 0) for s in samples)
geom_pcts = [
    float((s.get("yolo") or {}).get("geometry_coverage_pct") or 0)
    for s in samples
    if (s.get("yolo") or {}).get("sessions")
]
no_log_probes = sum(1 for s in samples if (s.get("yolo") or {}).get("note"))

# Full docker log blind analysis since start
blind_fp = 0
blind_sessions = 0
sessions_with_raw = 0
sessions_parsed = 0
if started:
    r = subprocess.run(
        ["docker", "logs", "birdlense", "--since", started[:19]],
        capture_output=True,
        text=True,
        timeout=180,
    )
    for line in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
        if "recording_session_summary" not in line:
            continue
        i = line.find("{")
        if i < 0:
            continue
        try:
            s = json.loads(line[i:])
        except Exception:
            continue
        sessions_parsed += 1
        raw = int(s.get("yolo_raw_boxes_total") or 0)
        tr = int(s.get("yolo_frames_with_tracks") or 0)
        if raw > 0 or tr > 0:
            sessions_with_raw += 1
        if s.get("yolo_blind_suspected") and (raw > 0 or tr > 0):
            blind_fp += 1
        if s.get("yolo_blind_suspected"):
            blind_sessions += 1

geom_cov = round(100.0 * sessions_with_raw / sessions_parsed, 1) if sessions_parsed else None

# DB since start
con = sqlite3.connect(str(db_path))
con.row_factory = sqlite3.Row
new_v = con.execute(
    "SELECT id, behavior_label, behavior_shadow_label, behavior_shadow_confidence, created_at "
    "FROM video WHERE deleted_at IS NULL AND created_at >= ? ORDER BY id",
    (started,),
).fetchall()
with_tracks = 0
for v in new_v:
    n = con.execute(
        "SELECT COUNT(*) FROM video_species WHERE video_id=? AND frames IS NOT NULL",
        (int(v["id"]),),
    ).fetchone()[0]
    if n > 0:
        with_tracks += 1
con.close()

n_new = len(new_v)
n_shadow = sum(1 for v in new_v if v["behavior_shadow_label"])
n_disc = sum(
    1
    for v in new_v
    if v["behavior_label"]
    and v["behavior_shadow_label"]
    and str(v["behavior_label"]).lower() != str(v["behavior_shadow_label"]).lower()
)
need_shadow = with_tracks
success_rate = round(100.0 * n_shadow / need_shadow, 1) if need_shadow else (100.0 if n_new == 0 else None)

harvest = d.get("harvest_total") or {}

canary_ok = success_rate is not None and (need_shadow == 0 or success_rate >= 95.0)
blind_ok = blind_fp == 0
monitor_ok = len(samples) >= 7 and no_log_probes < len(samples)  # expect ~8 probes for 2h/15m

verdict = "READY_FOR_8H_MARATHON" if (canary_ok and blind_ok and monitor_ok) else "BLOCKED"

lines = [
    "# Validation 2h Report",
    "",
    f"- **Window:** {started} → {ended}",
    f"- **Metrics file:** `{metrics_path}`",
    "",
    "## Status",
    "",
    "| Component | Status | Detail |",
    "|-----------|--------|--------|",
    f"| Canary Persist | {'OK' if canary_ok else 'FAIL'} | {n_shadow}/{need_shadow} videos with tracks got shadow ({success_rate}% success) |",
    f"| Blind Logic | {'OK' if blind_ok else 'FAIL'} | false positives (suspected + boxes): **{blind_fp}** (sessions parsed: {sessions_parsed}) |",
    f"| Monitor | {'OK' if monitor_ok else 'FAIL'} | probes={len(samples)}, no-log probes={no_log_probes} |",
    "",
    "## Canary",
    "",
    f"- New videos: **{n_new}**",
    f"- With tracks: **{with_tracks}**",
    f"- With `behavior_shadow_label`: **{n_shadow}**",
    f"- Discrepancies (meta≠shadow): **{n_disc}**",
    "",
    "### Examples",
    "",
]
for v in new_v[:10]:
    lines.append(
        f"- video **{v['id']}**: meta=`{v['behavior_label']}` shadow=`{v['behavior_shadow_label']}` "
        f"conf={v['behavior_shadow_confidence']}"
    )

lines += [
    "",
    "## YOLO",
    "",
    f"- Session summaries (full window): **{sessions_parsed}**",
    f"- Geometry coverage (sessions with raw boxes or tracks): **{geom_cov}%**",
    f"- Probe-session sum (interval windows): **{sess_total}**",
    f"- Blind suspected with boxes (false positive): **{blind_fp}**",
    "",
    "## Harvest",
    "",
    f"```json\n{json.dumps(harvest, indent=2)}\n```",
    "",
    f"## Verdict: **{verdict}**",
    "",
]
if verdict == "READY_FOR_8H_MARATHON":
    lines.append("All critical checks passed. Safe to schedule 8h nightly marathon for flying data collection.")
else:
    lines.append("Fix blockers before 8h marathon. See FAIL rows above.")

report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({
    "verdict": verdict,
    "canary_ok": canary_ok,
    "blind_ok": blind_ok,
    "monitor_ok": monitor_ok,
    "n_new": n_new,
    "n_shadow": n_shadow,
    "success_rate": success_rate,
    "blind_fp": blind_fp,
    "report": str(report_path),
}, indent=2))
PY

echo "Report: $REPORT"
