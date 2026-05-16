#!/usr/bin/env python3
"""Build detector continuity report from BirdLense SQLite."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _has_valid_bbox_frames(frames_raw: Any) -> bool:
    if frames_raw is None:
        return False
    text = str(frames_raw).strip()
    if not text:
        return False
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return False
    if not isinstance(data, list) or not data:
        return False
    for frame in data:
        if not isinstance(frame, dict):
            continue
        bbox = frame.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            coords = [float(x) for x in bbox]
        except (TypeError, ValueError):
            continue
        if coords[2] > coords[0] and coords[3] > coords[1]:
            return True
    return False


def _safe_rate(ok_count: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(float(ok_count) / float(total), 6)


def _load_clip_runtime_flags(
    conn: sqlite3.Connection,
    *,
    cutoff_iso: str,
) -> dict[str, int]:
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
    out = {
        "clip_count": 0,
        "clips_with_persisted_tracks": 0,
        "clips_with_yolo_frames": 0,
        "clips_with_yolo_tracks": 0,
    }
    seen_video_ids: set[int] = set()
    for (raw_payload,) in rows:
        try:
            payload = json.loads(raw_payload or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        ctx = payload.get("recording_context") or {}
        if str(ctx.get("triggered_by") or "live") == "track_regen":
            continue
        video_id = payload.get("video_id")
        try:
            video_id_i = int(video_id)
        except (TypeError, ValueError):
            continue
        if video_id_i in seen_video_ids:
            continue
        seen_video_ids.add(video_id_i)
        out["clip_count"] += 1
        persisted = payload.get("persisted_tracks") or payload.get("accepted_tracks") or []
        if isinstance(persisted, list) and persisted:
            out["clips_with_persisted_tracks"] += 1
        runtime = ctx.get("runtime_signals") or {}
        try:
            yolo_frames_ran = int(runtime.get("yolo_frames_ran") or 0)
            yolo_frames_with_tracks = int(runtime.get("yolo_frames_with_tracks") or 0)
        except (TypeError, ValueError):
            yolo_frames_ran = 0
            yolo_frames_with_tracks = 0
        if yolo_frames_ran > 0:
            out["clips_with_yolo_frames"] += 1
        if yolo_frames_with_tracks > 0:
            out["clips_with_yolo_tracks"] += 1
    return out


def build_detector_continuity_report(
    *,
    db_path: str,
    days: int = 14,
    min_track_ratio: float = 0.98,
    min_crop_ratio: float = 0.98,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window_days = max(1, int(days or 1))
    cutoff = now_utc - timedelta(days=window_days)
    cutoff_iso = cutoff.isoformat()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              vs.id AS video_species_id,
              vs.video_id AS video_id,
              vs.detection_provider AS detection_provider,
              vs.track_id AS track_id,
              vs.frames AS frames,
              v.start_time AS video_start_time
            FROM video_species vs
            JOIN video v ON v.id = vs.video_id
            WHERE vs.source = 'video'
              AND v.start_time >= ?
            ORDER BY vs.id DESC
            """,
            (cutoff_iso,),
        ).fetchall()

        provider_counts: Counter[str] = Counter()
        yolo_total = 0
        yolo_with_track = 0
        yolo_with_bbox = 0
        failing_examples: list[dict[str, Any]] = []

        for row in rows:
            provider = str(row["detection_provider"] or "unknown").strip().lower()
            provider_counts[provider or "unknown"] += 1
            track_id_raw = row["track_id"]
            has_bbox = _has_valid_bbox_frames(row["frames"])

            is_yolo_like = provider in {"yolo", "legacy", "unknown", ""}
            if not is_yolo_like:
                continue
            yolo_total += 1
            has_track = False
            try:
                has_track = int(track_id_raw) > 0
            except (TypeError, ValueError):
                has_track = False
            if has_track:
                yolo_with_track += 1
            if has_bbox:
                yolo_with_bbox += 1
            if (not has_track or not has_bbox) and len(failing_examples) < 20:
                failing_examples.append(
                    {
                        "video_species_id": int(row["video_species_id"]),
                        "video_id": int(row["video_id"]),
                        "provider": provider or "unknown",
                        "has_track_id": has_track,
                        "has_bbox_frames": has_bbox,
                    },
                )

        clip_stats = _load_clip_runtime_flags(conn, cutoff_iso=cutoff_iso)
    finally:
        conn.close()

    track_ratio = _safe_rate(yolo_with_track, yolo_total)
    crop_ratio = _safe_rate(yolo_with_bbox, yolo_total)
    report = {
        "schema": "detector_continuity_report@v1",
        "generated_at": now_utc.isoformat(),
        "window_days": window_days,
        "source_db": str(Path(db_path).resolve()),
        "slo": {
            "min_track_ratio": float(min_track_ratio),
            "min_crop_ratio": float(min_crop_ratio),
        },
        "rows": {
            "video_rows_total": int(len(rows)),
            "yolo_like_rows_total": int(yolo_total),
            "yolo_like_rows_with_track_id": int(yolo_with_track),
            "yolo_like_rows_with_bbox_frames": int(yolo_with_bbox),
            "provider_counts": dict(sorted(provider_counts.items())),
        },
        "clip_runtime": clip_stats,
        "metrics": {
            "track_continuity_ratio": track_ratio,
            "crop_continuity_ratio": crop_ratio,
            "track_gate_ok": bool(track_ratio >= float(min_track_ratio)),
            "crop_gate_ok": bool(crop_ratio >= float(min_crop_ratio)),
        },
        "failing_examples": failing_examples,
    }
    report["ok"] = bool(report["metrics"]["track_gate_ok"] and report["metrics"]["crop_gate_ok"])
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to birdlense.db")
    parser.add_argument("--days", type=int, default=14, help="Window size in days")
    parser.add_argument(
        "--min-track-ratio",
        type=float,
        default=0.98,
        help="Gate: minimum ratio of YOLO-like rows with positive track_id",
    )
    parser.add_argument(
        "--min-crop-ratio",
        type=float,
        default=0.98,
        help="Gate: minimum ratio of YOLO-like rows with valid bbox frames",
    )
    parser.add_argument("--out", default="", help="Optional path to write report JSON")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_detector_continuity_report(
        db_path=args.db,
        days=args.days,
        min_track_ratio=args.min_track_ratio,
        min_crop_ratio=args.min_crop_ratio,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    out = str(args.out or "").strip()
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
