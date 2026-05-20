#!/usr/bin/env python3
"""Build Golden Dataset v2 from session metrics + DB (bird / noise / hard)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class GoldenV2Clip:
    clip_id: str
    video_path: str | None
    is_bird: bool
    difficulty: str  # easy | hard
    category: str  # bird_confirmed | noise_fp | hard_scene
    source_ref: str
    yolo_raw: int | None = None
    yolo_accepted: int | None = None
    species: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _sha(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def _pick_video(con: sqlite3.Connection, ts: str) -> sqlite3.Row | None:
    return con.execute(
        """
        SELECT id, video_path FROM video
        WHERE deleted_at IS NULL
          AND datetime(start_time) <= datetime(?)
          AND datetime(start_time) >= datetime(?, '-15 minutes')
        ORDER BY datetime(start_time) DESC LIMIT 1
        """,
        (ts, ts),
    ).fetchone()


def mine_bird_clips(con: sqlite3.Connection, cutoff: str, limit: int) -> list[GoldenV2Clip]:
    q = """
    SELECT vs.id, vs.created_at, vs.confidence, s.name AS species, v.video_path,
           m.yolo_raw_boxes_total, m.yolo_accepted_boxes_total
    FROM video_species vs
    JOIN species s ON s.id = vs.species_id
    JOIN video v ON v.id = vs.video_id
    LEFT JOIN session_runtime_metrics m ON m.id = (
        SELECT id FROM session_runtime_metrics
        WHERE datetime(created_at) <= datetime(vs.created_at)
        ORDER BY datetime(created_at) DESC LIMIT 1
    )
    WHERE datetime(vs.created_at) >= datetime(?)
      AND vs.source = 'video'
      AND vs.confidence >= 0.45
      AND lower(s.name) NOT IN ('bird', 'unknown', '')
      AND v.deleted_at IS NULL
    ORDER BY vs.confidence DESC
    LIMIT ?
    """
    out: list[GoldenV2Clip] = []
    for row in con.execute(q, (cutoff, limit)).fetchall():
        vp = str(row["video_path"] or "").replace("\\", "/")
        cid = f"bird-{_sha(vp or str(row['id']))}"
        out.append(
            GoldenV2Clip(
                clip_id=cid,
                video_path=vp or None,
                is_bird=True,
                difficulty="easy",
                category="bird_confirmed",
                source_ref=f"video_species:{row['id']}",
                yolo_raw=int(row["yolo_raw_boxes_total"] or 0),
                yolo_accepted=int(row["yolo_accepted_boxes_total"] or 0),
                species=row["species"],
            )
        )
    return out


def mine_noise_clips(con: sqlite3.Connection, cutoff: str, limit: int) -> list[GoldenV2Clip]:
    q = """
    SELECT id, created_at, yolo_raw_boxes_total, yolo_accepted_boxes_total, payload_json
    FROM session_runtime_metrics
    WHERE datetime(created_at) >= datetime(?)
      AND yolo_raw_boxes_total >= 80
      AND yolo_accepted_boxes_total <= 5
    ORDER BY yolo_raw_boxes_total DESC
    LIMIT ?
    """
    out: list[GoldenV2Clip] = []
    for row in con.execute(q, (cutoff, limit)).fetchall():
        video = _pick_video(con, str(row["created_at"]))
        vp = str(video["video_path"]).replace("\\", "/") if video else None
        cid = f"noise-{_sha(str(row['id']))}"
        diff = "hard" if int(row["yolo_accepted_boxes_total"] or 0) > 0 else "easy"
        out.append(
            GoldenV2Clip(
                clip_id=cid,
                video_path=vp,
                is_bird=False,
                difficulty=diff,
                category="noise_fp",
                source_ref=f"session:{row['id']}",
                yolo_raw=int(row["yolo_raw_boxes_total"] or 0),
                yolo_accepted=int(row["yolo_accepted_boxes_total"] or 0),
            )
        )
    return out


def mine_hard_clips(con: sqlite3.Connection, cutoff: str, limit: int) -> list[GoldenV2Clip]:
    q = """
    SELECT id, created_at, yolo_raw_boxes_total, yolo_accepted_boxes_total
    FROM session_runtime_metrics
    WHERE datetime(created_at) >= datetime(?)
      AND yolo_accepted_boxes_total BETWEEN 1 AND 80
      AND yolo_raw_boxes_total > yolo_accepted_boxes_total
    ORDER BY (yolo_raw_boxes_total - yolo_accepted_boxes_total) DESC
    LIMIT ?
    """
    out: list[GoldenV2Clip] = []
    for row in con.execute(q, (cutoff, limit)).fetchall():
        video = _pick_video(con, str(row["created_at"]))
        vp = str(video["video_path"]).replace("\\", "/") if video else None
        cid = f"hard-{_sha(str(row['id']))}"
        out.append(
            GoldenV2Clip(
                clip_id=cid,
                video_path=vp,
                is_bird=True,
                difficulty="hard",
                category="hard_scene",
                source_ref=f"session:{row['id']}",
                yolo_raw=int(row["yolo_raw_boxes_total"] or 0),
                yolo_accepted=int(row["yolo_accepted_boxes_total"] or 0),
            )
        )
    return out


def _dedupe(clips: list[GoldenV2Clip]) -> list[GoldenV2Clip]:
    seen: set[str] = set()
    out: list[GoldenV2Clip] = []
    for c in clips:
        key = c.video_path or c.clip_id
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="app/data/db/birdlense.db")
    p.add_argument("--output-dir", default="app/data/datasets/golden_v2")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--target-bird", type=int, default=20)
    p.add_argument("--target-noise", type=int, default=20)
    p.add_argument("--target-hard", type=int, default=10)
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"DB not found: {db_path}", flush=True)
        return 1

    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, args.days))).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    con = _connect(str(db_path))
    clips: list[GoldenV2Clip] = []
    clips.extend(mine_bird_clips(con, cutoff, args.target_bird))
    clips.extend(mine_noise_clips(con, cutoff, args.target_noise))
    clips.extend(mine_hard_clips(con, cutoff, args.target_hard))
    clips = _dedupe(clips)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cutoff_utc": cutoff,
        "clip_count": len(clips),
        "clips": [c.to_dict() for c in clips],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {manifest_path} ({len(clips)} clips)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
