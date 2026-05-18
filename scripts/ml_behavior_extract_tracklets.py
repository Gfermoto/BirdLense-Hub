#!/usr/bin/env python3
"""Extract behavior tracklet manifest from Hub SQLite detections (#456)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_frames(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        p = json.loads(raw)
    except Exception:
        return []
    return p if isinstance(p, list) else []


def _build_tracklet_row(row: sqlite3.Row, *, default_split: str, domain_tag: str) -> dict[str, Any] | None:
    frames = _parse_frames(row["frames"])
    if not frames:
        return None
    t_vals = []
    for f in frames:
        if not isinstance(f, dict):
            continue
        try:
            t_vals.append(float(f.get("t") or 0.0))
        except (TypeError, ValueError):
            continue
    if not t_vals:
        return None
    t_start_ms = int(max(0.0, min(t_vals)) * 1000.0)
    t_end_ms = int(max(0.0, max(t_vals)) * 1000.0)
    behavior_label = str(row["behavior_label"] or "").strip().lower() or None
    return {
        "tracklet_id": f"v{int(row['video_id'])}_t{int(row['track_id']) if row['track_id'] is not None else 'na'}_{int(row['video_species_id'])}",
        "video_id": int(row["video_id"]),
        "video_species_id": int(row["video_species_id"]),
        "track_id": int(row["track_id"]) if row["track_id"] is not None else None,
        "camera_id": None,
        "video_path": str(row["video_path"]),
        "t_start_ms": t_start_ms,
        "t_end_ms": t_end_ms,
        "frame_count": len(frames),
        "boxes": frames,
        "species_name": str(row["species_name"] or "").strip() or None,
        "label": behavior_label,
        "label_source": "video_behavior_label" if behavior_label else "unlabeled",
        "split": default_split,
        "domain_tag": domain_tag,
    }


def build_behavior_tracklet_manifest(
    *,
    db_path: Path,
    out_path: Path,
    min_frames: int = 5,
    split: str = "train",
    domain_tag: str = "hub_feeder",
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
          vs.id AS video_species_id,
          vs.video_id,
          vs.track_id,
          vs.frames,
          s.name AS species_name,
          v.video_path,
          v.behavior_label
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        LEFT JOIN species s ON s.id = vs.species_id
        WHERE vs.source='video'
          AND v.deleted_at IS NULL
          AND vs.frames IS NOT NULL
        ORDER BY vs.id ASC
        """
    ).fetchall()

    tracklets = []
    for row in rows:
        tr = _build_tracklet_row(row, default_split=split, domain_tag=domain_tag)
        if tr is None:
            continue
        if int(tr["frame_count"]) < int(min_frames):
            continue
        tracklets.append(tr)

    label_counts: dict[str, int] = {}
    for tr in tracklets:
        lab = str(tr.get("label") or "unlabeled")
        label_counts[lab] = label_counts.get(lab, 0) + 1

    manifest = {
        "schema": "behavior_tracklet_manifest@v1",
        "created_at": _utc_now(),
        "source": "birdlense_hub",
        "db_path": str(db_path),
        "tracklet_count": len(tracklets),
        "label_counts": label_counts,
        "tracklets": tracklets,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="Path to birdlense.db")
    ap.add_argument("--out", required=True, help="Output behavior_tracklet_manifest@v1 JSON")
    ap.add_argument("--min-frames", type=int, default=5)
    ap.add_argument("--split", default="train")
    ap.add_argument("--domain-tag", default="hub_feeder")
    args = ap.parse_args()

    db = Path(args.db).expanduser().resolve()
    if not db.is_file():
        raise SystemExit(f"DB not found: {db}")
    out = Path(args.out).expanduser().resolve()
    man = build_behavior_tracklet_manifest(
        db_path=db,
        out_path=out,
        min_frames=max(1, int(args.min_frames)),
        split=str(args.split).strip() or "train",
        domain_tag=str(args.domain_tag).strip() or "hub_feeder",
    )
    print(json.dumps({"ok": True, "out": str(out), "tracklet_count": man["tracklet_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
