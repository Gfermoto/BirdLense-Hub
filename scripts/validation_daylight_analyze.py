#!/usr/bin/env python3
"""Analyze daylight 2h validation JSON + DB + docker logs."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--db", default="/root/BirdLense/app/data/db/birdlense.db")
    ap.add_argument("--report", required=True)
    ap.add_argument("--container", default="birdlense")
    args = ap.parse_args()

    metrics_path = Path(args.metrics)
    report_path = Path(args.report)
    d = json.loads(metrics_path.read_text())
    started = str(d.get("started_at") or "")
    ended = str(d.get("ended_at") or started)
    samples = d.get("samples") or []

    sess_probe_sum = sum(int((s.get("yolo") or {}).get("sessions") or 0) for s in samples)
    no_log = sum(1 for s in samples if (s.get("yolo") or {}).get("note"))
    probe_sessions = [int((s.get("yolo") or {}).get("sessions") or 0) for s in samples]

    blind_fp = 0
    sessions_parsed = 0
    with_boxes = 0
    if started:
        r = subprocess.run(
            ["docker", "logs", args.container, "--since", started[:19]],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        for line in (r.stdout or "").splitlines():
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
            rf = int(s.get("yolo_frames_with_raw_boxes") or 0)
            if raw > 0 or tr > 0 or rf > 0:
                with_boxes += 1
            if s.get("yolo_blind_suspected") and (raw > 0 or tr > 0 or rf > 0):
                blind_fp += 1

    con = sqlite3.connect(args.db)
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
    need = with_tracks
    success_rate = round(100.0 * n_shadow / need, 1) if need else (100.0 if n_new == 0 else None)

    harvest = d.get("harvest_total") or {}
    crops_saved = int(harvest.get("saved") or 0)

    monitor_ok = len(samples) >= 10 and max(probe_sessions, default=0) > 0 and no_log < len(samples)
    blind_ok = blind_fp == 0
    canary_ok = need > 0 and success_rate is not None and success_rate >= 95.0
    canary_inconclusive = need == 0 and n_new == 0

    if canary_inconclusive:
        canary_status = "INCONCLUSIVE"
    elif canary_ok:
        canary_status = "OK"
    else:
        canary_status = "FAIL"

    if monitor_ok and blind_ok and canary_ok:
        verdict = "READY_FOR_8H_MARATHON"
    elif monitor_ok and blind_ok and canary_inconclusive:
        verdict = "PARTIAL_READY"
    else:
        verdict = "BLOCKED"

    geom_pct = round(100.0 * with_boxes / sessions_parsed, 1) if sessions_parsed else None

    lines = [
        "# Validation Daylight — Fixes Report",
        "",
        f"- **Window (UTC):** {started} → {ended}",
        f"- **Metrics:** `{metrics_path}`",
        "",
        "## Fixes applied",
        "",
        "| Bug | Was | Fix |",
        "|-----|-----|-----|",
        "| Monitor | `\"2>&1\"` in argv / `capture_output`+stderr clash | `stdout=PIPE`, `stderr=STDOUT` |",
        "| Blind | `blind_suspected` from early `rs_ctx` copy | `_blind_suspected_from_final_stats()` at summary time |",
        "| Canary | 1-logit IR vs 2 labels | sigmoid mapping (prior deploy) |",
        "",
        "## KPI",
        "",
        "| Check | Status | Value |",
        "|-------|--------|-------|",
        f"| Monitor | {'OK' if monitor_ok else 'FAIL'} | probes={len(samples)}, max_sessions/probe={max(probe_sessions) if probe_sessions else 0}, no-log probes={no_log} |",
        f"| Blind FP | {'OK' if blind_ok else 'FAIL'} | {blind_fp} (goal 0), sessions={sessions_parsed} |",
        f"| Canary | {canary_status} | shadow {n_shadow}/{need} ({success_rate}%), new videos={n_new} |",
        f"| Harvest | {'OK' if crops_saved >= 1 else 'FAIL'} | saved={crops_saved} |",
        "",
        "## YOLO",
        "",
        f"- Geometry (sessions with boxes/tracks): **{geom_pct}%** ({with_boxes}/{sessions_parsed})",
        "",
        "## Examples (new videos)",
        "",
    ]
    for v in new_v[:12]:
        lines.append(
            f"- **{v['id']}**: meta=`{v['behavior_label']}` shadow=`{v['behavior_shadow_label']}` "
            f"conf={v['behavior_shadow_confidence']}"
        )
    if not new_v:
        lines.append("- _(none)_")

    lines += [
        "",
        "## Harvest",
        "",
        f"```json\n{json.dumps(harvest, indent=2)}\n```",
        "",
        f"## Verdict: **{verdict}**",
        "",
    ]
    if verdict == "READY_FOR_8H_MARATHON":
        lines.append(
            "Start 8h marathon:\n"
            "```bash\n"
            "bash scripts/nightly_marathon_start.sh\n"
            "```"
        )
    elif verdict == "PARTIAL_READY":
        lines.append("Monitor + blind OK; no new videos with tracks — repeat when birds are active or extend window.")
    else:
        lines.append("Fix remaining FAIL rows before 8h marathon.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "monitor_ok": monitor_ok,
                "blind_ok": blind_ok,
                "canary_status": canary_status,
                "n_new": n_new,
                "n_shadow": n_shadow,
                "blind_fp": blind_fp,
                "report": str(report_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
