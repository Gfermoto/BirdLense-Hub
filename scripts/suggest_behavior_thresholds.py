#!/usr/bin/env python3
"""Suggest LOW_CONFIDENCE and short-track thresholds from telemetry (#451/#467)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from statistics import median


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def suggest_thresholds(db_path: Path, *, lookback_hours: int = 72, limit: int = 2000) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, payload_json
        FROM session_runtime_metrics
        WHERE datetime(created_at) >= datetime('now', ?)
        ORDER BY id DESC
        LIMIT ?
        """,
        (f"-{max(1, int(lookback_hours))} hours", max(10, int(limit))),
    ).fetchall()

    blind_scores = []
    fallback_ratios = []
    low_conf_hits = 0
    short_track_hits = 0
    yolo_frames = 0
    for row in rows:
        try:
            p = json.loads(row["payload_json"] or "{}")
        except Exception:
            p = {}
        bs = p.get("yolo_blind_score")
        if bs is not None:
            blind_scores.append(_safe_float(bs))
        yolo = _safe_int(p.get("yolo_frames_ran"))
        fr_only = _safe_int(p.get("session_extended_by_frigate_only"))
        yolo_frames += max(0, yolo)
        if yolo > 0:
            fallback_ratios.append(max(0.0, min(1.0, _safe_float(fr_only) / float(yolo))))
        rej = p.get("fusion_rejections") or {}
        if isinstance(rej, dict):
            low_conf_hits += _safe_int(rej.get("LOW_CONFIDENCE"))
            short_track_hits += _safe_int(rej.get("REJECT_REJECTED_SHORT_TRACK"))

    blind_med = median(blind_scores) if blind_scores else 0.0
    fallback_med = median(fallback_ratios) if fallback_ratios else 0.0
    low_conf_ratio = (low_conf_hits / max(1, yolo_frames))
    short_track_ratio = (short_track_hits / max(1, yolo_frames))

    # Conservative auto-tune proposals for 7fps/low-res profile.
    min_conf_to_process = 0.18 + min(0.12, low_conf_ratio * 4.0) - min(0.04, fallback_med * 0.08)
    min_track_duration = 2 + int(round(min(4.0, short_track_ratio * 40.0 + blind_med * 1.5)))
    min_track_duration = max(1, min(8, min_track_duration))

    out = {
        "schema": "behavior_threshold_suggestion@v1",
        "rows_analyzed": len(rows),
        "metrics": {
            "blind_score_median": round(blind_med, 6),
            "fallback_ratio_median": round(fallback_med, 6),
            "low_conf_ratio": round(low_conf_ratio, 6),
            "short_track_ratio": round(short_track_ratio, 6),
        },
        "suggested_config": {
            "processor.min_confidence_to_process": round(max(0.12, min(0.45, min_conf_to_process)), 4),
            "processor.min_track_duration": int(min_track_duration),
        },
    }
    conn.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--lookback-hours", type=int, default=72)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    db = Path(args.db).expanduser().resolve()
    if not db.is_file():
        raise SystemExit(f"db not found: {db}")
    out = suggest_thresholds(
        db,
        lookback_hours=max(1, int(args.lookback_hours)),
        limit=max(10, int(args.limit)),
    )
    if args.out:
        op = Path(args.out).expanduser().resolve()
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
