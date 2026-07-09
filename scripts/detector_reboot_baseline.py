#!/usr/bin/env python3
"""Detector reboot baseline report for BirdBox/Forest windows."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_decision_trace_rows(
    conn: sqlite3.Connection,
    cutoff_iso: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT data
        FROM activity_log
        WHERE type = 'decision_trace'
          AND created_at >= ?
        ORDER BY created_at DESC
        """,
        (cutoff_iso,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for (raw_data,) in rows:
        try:
            payload = json.loads(raw_data or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def build_report(
    *,
    db_path: Path,
    days: int,
    cameras: list[str],
) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=max(1, int(days)))
    cutoff_iso = cutoff.isoformat()

    conn = sqlite3.connect(str(db_path))
    try:
        traces = _load_decision_trace_rows(conn, cutoff_iso)
    finally:
        conn.close()

    target_cameras = {c.strip() for c in cameras if c.strip()}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for trace in traces:
        rc = trace.get("recording_context") or {}
        cam = str(trace.get("camera_id") or rc.get("camera_id") or "").strip()
        if not cam:
            cam = "unknown"
        if target_cameras and cam not in target_cameras:
            continue
        grouped[cam].append(trace)

    camera_reports: dict[str, dict[str, Any]] = {}
    global_sessions = 0
    global_zero_accepted = 0

    for camera_id, camera_traces in grouped.items():
        sessions = 0
        zero_accepted = 0
        trigger_counts: dict[str, int] = defaultdict(int)
        raw_total = 0
        accepted_total = 0
        panic_candidates = 0

        for trace in camera_traces:
            rc = trace.get("recording_context") or {}
            runtime = rc.get("runtime_signals") or {}
            sessions += 1
            trigger = (
                str(rc.get("triggered_by") or "unknown").strip().lower()
                or "unknown"
            )
            trigger_counts[trigger] += 1

            raw = _safe_int(runtime.get("yolo_raw_boxes_total"))
            accepted = _safe_int(runtime.get("yolo_accepted_boxes_total"))
            frigate_only = _safe_int(
                runtime.get("session_extended_by_frigate_only")
            )

            raw_total += raw
            accepted_total += accepted
            if accepted <= 0:
                zero_accepted += 1
            if frigate_only > 0 and accepted <= 0:
                panic_candidates += 1

        global_sessions += sessions
        global_zero_accepted += zero_accepted
        camera_reports[camera_id] = {
            "sessions": sessions,
            "zero_accepted_sessions": zero_accepted,
            "zero_accepted_ratio": round(
                float(zero_accepted) / float(max(1, sessions)),
                6,
            ),
            "trigger_counts": dict(sorted(trigger_counts.items())),
            "yolo_raw_boxes_total": raw_total,
            "yolo_accepted_boxes_total": accepted_total,
            "raw_to_accepted_ratio": round(
                float(raw_total) / float(max(1, accepted_total)),
                6,
            ),
            "panic_candidates_frigate_without_hub": panic_candidates,
        }

    return {
        "schema": "detector_reboot_baseline@v1",
        "generated_at": now_utc.isoformat(),
        "window_days": max(1, int(days)),
        "source_db": str(db_path.resolve()),
        "cameras": camera_reports,
        "global": {
            "sessions": global_sessions,
            "zero_accepted_sessions": global_zero_accepted,
            "zero_accepted_ratio": round(
                float(global_zero_accepted) / float(max(1, global_sessions)),
                6,
            ),
        },
    }


def _default_db_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "app" / "data" / "db" / "birdlense.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Analysis window in days.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=_default_db_path(),
        help="Path to BirdLense SQLite DB.",
    )
    parser.add_argument(
        "--cameras",
        default="BirdBox,Forest",
        help="Comma-separated camera ids.",
    )
    args = parser.parse_args()

    cameras = [x.strip() for x in str(args.cameras).split(",") if x.strip()]
    report = build_report(
        db_path=args.db_path,
        days=args.days,
        cameras=cameras,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
