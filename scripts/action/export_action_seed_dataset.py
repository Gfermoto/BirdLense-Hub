#!/usr/bin/env python3
# flake8: noqa
"""Export weak-labeled action seed dataset rows from SQLite."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TrackRow:
    track_id: int | None
    start_time: float
    end_time: float


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(r[1]) for r in rows}


def _parse_video_ids(raw: str) -> list[int]:
    out: list[int] = []
    for chunk in (raw or "").split(","):
        s = chunk.strip()
        if not s:
            continue
        out.append(int(s))
    return out


def _camera_id(video_row: sqlite3.Row, video_cols: set[str]) -> str:
    if "camera_id" in video_cols and video_row["camera_id"] is not None:
        return str(video_row["camera_id"])
    if "camera_name" in video_cols and video_row["camera_name"] is not None:
        return str(video_row["camera_name"])
    if "video_path" in video_cols and video_row["video_path"]:
        path = str(video_row["video_path"]).replace("\\", "/")
        if "/" in path:
            return path.rsplit("/", 1)[0]
        return path
    return "unknown_camera"


def _segment_uid(
    *,
    video_id: int,
    track_id: int | None,
    label: str,
    t_start_ms: int,
    t_end_ms: int,
) -> str:
    return f"v{video_id}:t{track_id if track_id is not None else -1}:{label}:{t_start_ms}:{t_end_ms}"


def _mk_row(
    *,
    video_id: int,
    track_id: int | None,
    camera_id: str,
    action_label: str,
    t_start_ms: int,
    t_end_ms: int,
    confidence: float,
    annotator_id: str,
    source: str,
) -> dict[str, Any]:
    return {
        "segment_uid": _segment_uid(
            video_id=video_id,
            track_id=track_id,
            label=action_label,
            t_start_ms=t_start_ms,
            t_end_ms=t_end_ms,
        ),
        "video_id": int(video_id),
        "track_id": int(track_id) if track_id is not None else None,
        "camera_id": camera_id,
        "action_label": action_label,
        "t_start_ms": int(t_start_ms),
        "t_end_ms": int(t_end_ms),
        "confidence": float(confidence),
        "annotator_id": annotator_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }


def export_seed_rows(
    *,
    db_path: Path,
    output_jsonl: Path,
    manifest_json: Path | None,
    limit_videos: int,
    boundary_ms: int,
    min_track_duration_ms: int,
    min_tracks: int,
    min_weight_delta_kg: float,
    require_weight_delta: bool,
    annotator_id: str,
    video_ids: list[int],
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    video_cols = _table_columns(conn, "video")

    where_clauses: list[str] = []
    args: list[Any] = []
    if video_ids:
        where_clauses.append(f"v.id IN ({','.join('?' for _ in video_ids)})")
        args.extend([int(v) for v in video_ids])

    if require_weight_delta:
        where_clauses.append("abs(COALESCE(v.scales_weight_delta_kg, 0.0)) >= ?")
        args.append(float(min_weight_delta_kg))

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    q = f"""
        SELECT
            v.id AS video_id,
            COALESCE(v.scales_weight_delta_kg, 0.0) AS scales_weight_delta_kg,
            {("v.camera_id AS camera_id," if "camera_id" in video_cols else "")}
            {("v.camera_name AS camera_name," if "camera_name" in video_cols else "")}
            {("v.video_path AS video_path," if "video_path" in video_cols else "")}
            COUNT(vs.id) AS track_count
        FROM video v
        JOIN video_species vs ON vs.video_id = v.id
        {where_sql}
        GROUP BY v.id
        HAVING COUNT(vs.id) >= ?
        ORDER BY v.id DESC
        LIMIT ?
    """
    args.extend([int(min_tracks), int(limit_videos)])
    video_rows = conn.execute(q, args).fetchall()

    rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    used_videos = 0
    feeding_videos = 0
    for v in video_rows:
        tracks_raw = conn.execute(
            """
            SELECT track_id, start_time, end_time
            FROM video_species
            WHERE video_id = ?
            ORDER BY start_time ASC, id ASC
            """,
            (int(v["video_id"]),),
        ).fetchall()
        tracks: list[TrackRow] = []
        for tr in tracks_raw:
            try:
                st = float(tr["start_time"])
                en = float(tr["end_time"])
            except Exception:
                continue
            if en <= st:
                continue
            if int((en - st) * 1000.0) < int(min_track_duration_ms):
                continue
            tracks.append(TrackRow(track_id=tr["track_id"], start_time=st, end_time=en))
        if not tracks:
            continue

        used_videos += 1
        camera_id = _camera_id(v, video_cols)
        first = tracks[0]
        last = tracks[-1]
        arrival_t0 = max(0, int(first.start_time * 1000.0))
        arrival_t1 = arrival_t0 + int(boundary_ms)
        departure_t1 = max(0, int(last.end_time * 1000.0))
        departure_t0 = max(0, departure_t1 - int(boundary_ms))

        arr = _mk_row(
            video_id=int(v["video_id"]),
            track_id=first.track_id,
            camera_id=camera_id,
            action_label="arrival",
            t_start_ms=arrival_t0,
            t_end_ms=arrival_t1,
            confidence=0.55,
            annotator_id=annotator_id,
            source="weak_label:first_track_start",
        )
        dep = _mk_row(
            video_id=int(v["video_id"]),
            track_id=last.track_id,
            camera_id=camera_id,
            action_label="departure",
            t_start_ms=departure_t0,
            t_end_ms=departure_t1,
            confidence=0.50,
            annotator_id=annotator_id,
            source="weak_label:last_track_end",
        )
        rows.extend([arr, dep])
        label_counts.update(["arrival", "departure"])

        weight_delta = float(v["scales_weight_delta_kg"] or 0.0)
        if abs(weight_delta) >= float(min_weight_delta_kg):
            mid = (first.start_time + last.end_time) / 2.0
            t0 = max(0, int(mid * 1000.0) - int(boundary_ms // 2))
            t1 = t0 + int(boundary_ms)
            feed = _mk_row(
                video_id=int(v["video_id"]),
                track_id=first.track_id,
                camera_id=camera_id,
                action_label="possible_feeding",
                t_start_ms=t0,
                t_end_ms=t1,
                confidence=0.50,
                annotator_id=annotator_id,
                source=f"weak_label:feeder_weight_delta={weight_delta}",
            )
            rows.append(feed)
            label_counts.update(["possible_feeding"])
            feeding_videos += 1

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "schema": "action_seed_export@v1",
        "db_path": str(db_path),
        "output_jsonl": str(output_jsonl),
        "row_count": len(rows),
        "video_count": used_videos,
        "feeding_video_count": feeding_videos,
        "labels": dict(label_counts),
        "params": {
            "limit_videos": int(limit_videos),
            "boundary_ms": int(boundary_ms),
            "min_track_duration_ms": int(min_track_duration_ms),
            "min_tracks": int(min_tracks),
            "min_weight_delta_kg": float(min_weight_delta_kg),
            "require_weight_delta": bool(require_weight_delta),
            "annotator_id": annotator_id,
            "video_ids": [int(v) for v in video_ids],
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    if manifest_json:
        manifest_json.parent.mkdir(parents=True, exist_ok=True)
        manifest_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--manifest-json", default="")
    parser.add_argument("--limit-videos", type=int, default=400)
    parser.add_argument("--boundary-ms", type=int, default=300)
    parser.add_argument("--min-track-duration-ms", type=int, default=300)
    parser.add_argument("--min-tracks", type=int, default=1)
    parser.add_argument("--min-weight-delta-kg", type=float, default=0.001)
    parser.add_argument("--require-weight-delta", action="store_true")
    parser.add_argument("--annotator-id", default="bootstrap_weak_label")
    parser.add_argument(
        "--video-ids",
        default="",
        help="Comma-separated ids to constrain export.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.boundary_ms < 300:
        raise SystemExit("boundary-ms must be >= 300")
    if args.min_track_duration_ms < 300:
        raise SystemExit("min-track-duration-ms must be >= 300")
    summary = export_seed_rows(
        db_path=Path(args.db_path).resolve(),
        output_jsonl=Path(args.output_jsonl).resolve(),
        manifest_json=Path(args.manifest_json).resolve() if args.manifest_json else None,
        limit_videos=int(args.limit_videos),
        boundary_ms=int(args.boundary_ms),
        min_track_duration_ms=int(args.min_track_duration_ms),
        min_tracks=int(args.min_tracks),
        min_weight_delta_kg=float(args.min_weight_delta_kg),
        require_weight_delta=bool(args.require_weight_delta),
        annotator_id=str(args.annotator_id),
        video_ids=_parse_video_ids(str(args.video_ids)),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
