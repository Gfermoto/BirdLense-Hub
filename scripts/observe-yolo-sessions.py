#!/usr/bin/env python3
"""One-shot YOLO visibility report: docker session summaries + DB + product metrics."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _ssh(cmd: str, *, host: str, port: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-p", port, host, cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_session_summaries(log_text: str) -> list[dict]:
    out: list[dict] = []
    for line in log_text.splitlines():
        if "recording_session_summary" not in line:
            continue
        i = line.find("{")
        if i < 0:
            continue
        try:
            out.append(json.loads(line[i:]))
        except json.JSONDecodeError:
            continue
    return out


def _summarize_sessions(sessions: list[dict]) -> dict:
    if not sessions:
        return {"sessions": 0}
    yolo_ran = sum(int(s.get("yolo_frames_ran") or 0) for s in sessions)
    yolo_tr = sum(int(s.get("yolo_frames_with_tracks") or 0) for s in sessions)
    raw_frames = sum(int(s.get("yolo_frames_with_raw_boxes") or 0) for s in sessions)
    raw_boxes = sum(int(s.get("yolo_raw_boxes_total") or 0) for s in sessions)
    accepted = sum(int(s.get("yolo_accepted_boxes_total") or 0) for s in sessions)
    bt = sum(int(s.get("bytetrack_rows") or 0) for s in sessions)
    persist = sum(int(s.get("post_fusion_persisted") or 0) for s in sessions)
    mqtt = sum(int(s.get("mqtt_events_in_window") or 0) for s in sessions)
    with_tr = sum(1 for s in sessions if int(s.get("yolo_frames_with_tracks") or 0) > 0)
    with_raw = sum(1 for s in sessions if int(s.get("yolo_frames_with_raw_boxes") or 0) > 0)
    return {
        "sessions": len(sessions),
        "yolo_frames_ran": yolo_ran,
        "yolo_frames_with_tracks": yolo_tr,
        "yolo_frames_with_raw_boxes": raw_frames,
        "yolo_raw_boxes_total": raw_boxes,
        "yolo_accepted_boxes_total": accepted,
        "sessions_with_tracks": with_tr,
        "sessions_with_raw_boxes": with_raw,
        "bytetrack_rows": bt,
        "post_fusion_persisted": persist,
        "mqtt_events": mqtt,
        "track_rate_pct": round(100.0 * yolo_tr / yolo_ran, 2) if yolo_ran else None,
        "raw_frame_rate_pct": round(100.0 * raw_frames / yolo_ran, 2) if yolo_ran else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="6h", help="docker logs --since (default 6h)")
    ap.add_argument("--db-days", type=int, default=3, help="report-yolo-product-metrics window")
    ap.add_argument("--host", default=_env("DEPLOY_HOST", "root@185.218.111.196"))
    ap.add_argument("--port", default=_env("DEPLOY_SSH_PORT", "2222"))
    ap.add_argument("--remote-dir", default=_env("DEPLOY_REMOTE_DIR", "/root/BirdLense"))
    ap.add_argument("--json-out", default="", help="optional path to write full report JSON")
    args = ap.parse_args()

    rdir = args.remote_dir
    logs = _ssh(f"docker logs birdlense --since {args.since} 2>&1", host=args.host, port=args.port)
    log_text = (logs.stdout or "") + (logs.stderr or "")
    sessions = _parse_session_summaries(log_text)
    session_agg = _summarize_sessions(sessions)

    db_script = (
        "python3 - <<'PY'\n"
        "import sqlite3, json\n"
        f"con=sqlite3.connect('{rdir}/app/data/db/birdlense.db')\n"
        "con.row_factory=sqlite3.Row\n"
        "prov=[dict(r) for r in con.execute(\"\"\"\n"
        "SELECT COALESCE(detection_provider,'?') p, COUNT(*) n FROM video_species vs\n"
        "JOIN video v ON v.id=vs.video_id WHERE v.created_at>=datetime('now','-48 hours')\n"
        "GROUP BY p ORDER BY n DESC\"\"\")]\n"
        "print(json.dumps({'providers_48h': prov}, ensure_ascii=False))\n"
        "PY"
    )
    db_r = _ssh(db_script, host=args.host, port=args.port)
    providers = {}
    if db_r.returncode == 0:
        try:
            providers = json.loads((db_r.stdout or "{}").strip() or "{}")
        except json.JSONDecodeError:
            providers = {"error": (db_r.stdout or "")[:200]}

    metrics_r = _ssh(
        f"cd {rdir} && python3 scripts/report-yolo-product-metrics.py "
        f"--db app/data/db/birdlense.db --days {args.db_days}",
        host=args.host,
        port=args.port,
    )
    product = {}
    if metrics_r.returncode == 0:
        try:
            product = json.loads((metrics_r.stdout or "{}").strip() or "{}")
        except json.JSONDecodeError:
            product = {"error": (metrics_r.stdout or "")[:300]}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": args.since,
        "sessions": session_agg,
        "last_sessions": sessions[-5:],
        **providers,
        "product_metrics": product,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        out = Path(args.json_out)
        if not out.is_absolute():
            out = REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
