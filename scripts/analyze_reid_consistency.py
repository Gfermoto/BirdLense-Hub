#!/usr/bin/env python3
"""Analyze ReID nickname consistency and emit hard cases for review."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


def _norm_label(raw: Any) -> str:
    return str(raw or "").strip()


def analyze(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
          video_species_id,
          video_id,
          track_id,
          species_name,
          individual_label,
          created_at
        FROM reid_embedding
        """
    ).fetchall()

    by_video_track: dict[tuple[int, int], set[str]] = defaultdict(set)
    by_video_species: dict[int, set[str]] = defaultdict(set)
    hard_cases: list[dict[str, Any]] = []

    for row in rows:
        label = _norm_label(row["individual_label"])
        if not label:
            continue
        video_id = row["video_id"]
        track_id = row["track_id"]
        vsid = row["video_species_id"]
        if isinstance(video_id, int) and isinstance(track_id, int):
            by_video_track[(video_id, track_id)].add(label)
        if isinstance(vsid, int):
            by_video_species[vsid].add(label)

    for (video_id, track_id), labels in sorted(by_video_track.items()):
        if len(labels) <= 1:
            continue
        hard_cases.append(
            {
                "reason_code": "reid_conflict_same_track",
                "video_id": video_id,
                "track_id": track_id,
                "labels": sorted(labels),
            }
        )

    for vsid, labels in sorted(by_video_species.items()):
        if len(labels) <= 1:
            continue
        hard_cases.append(
            {
                "reason_code": "reid_conflict_same_video_species",
                "video_species_id": vsid,
                "labels": sorted(labels),
            }
        )

    report = {
        "schema": "reid_consistency_report@v1",
        "db_path": str(db_path),
        "rows_total": len(rows),
        "hard_cases_count": len(hard_cases),
        "hard_cases": hard_cases,
    }
    conn.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="Path to birdlense.db")
    ap.add_argument("--out", help="Output JSON path")
    args = ap.parse_args()

    db = Path(args.db).expanduser().resolve()
    if not db.is_file():
        raise SystemExit(f"DB not found: {db}")

    report = analyze(db)
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "out": str(out), "hard_cases_count": report["hard_cases_count"]}, ensure_ascii=False))
        return 0

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
