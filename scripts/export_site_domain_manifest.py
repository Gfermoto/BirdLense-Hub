#!/usr/bin/env python3
"""Export camera-agnostic site-domain crop manifest from SQLite (Hub path).

Does not require Frigate. Prefer rows with classifier_needs_review or named species.
See benchmarks/site_domain_schema.json.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="path to birdlense.db")
    ap.add_argument("--out", default="benchmarks/site_domain_manifest.jsonl")
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT v.id AS video_id,
               lower(coalesce(s.name, '')) AS species_name,
               vs.confidence AS confidence,
               v.start_time AS start_time,
               v.video_path AS video_path
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        JOIN species s ON s.id = vs.species_id
        WHERE v.start_time >= datetime('now', ?)
        ORDER BY v.start_time DESC
        LIMIT ?
        """,
        (f"-{int(args.days)} days", int(args.limit)),
    ).fetchall()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            sp = str(r["species_name"] or "")
            label_source = "unknown"
            needs_review = sp in {"bird", "unknown", "unknown bird", ""}
            if not needs_review:
                label_source = "classifier"
            row = {
                "crop_id": f"vid{r['video_id']}",
                "species_name": sp or "Bird",
                "label_source": label_source,
                "needs_review": needs_review,
                "camera_id": None,
                "video_id": int(r["video_id"]),
                "track_id": None,
                "frame_t": None,
                "bbox_norm": None,
                "crop_path": None,
                "confidence": float(r["confidence"] or 0.0) if r["confidence"] is not None else None,
                "split": "review" if needs_review else "train",
                "site_id": None,
                "video_path": r["video_path"],
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    print(json.dumps({"wrote": n, "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
