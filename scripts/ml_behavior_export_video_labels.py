#!/usr/bin/env python3
"""Export video behavior labels from SQLite for training feedback (#416 Wave 5).

Writes JSONL lines: video_id, behavior_label, behavior_confidence, video_path, processor_version.
Uses stdlib sqlite3 only (no Flask).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> int:
    """CLI entry."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True, help="Path to birdlense.db")
    p.add_argument("--out", required=True, help="Output .jsonl path")
    p.add_argument("--require-confidence", action="store_true", help="Skip rows with null confidence")
    args = p.parse_args()
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.is_file():
        raise SystemExit(f"DB not found: {db_path}")
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT id, video_path, processor_version, behavior_label, behavior_confidence
        FROM video
        WHERE deleted_at IS NULL
          AND behavior_label IS NOT NULL
          AND TRIM(behavior_label) != ''
        ORDER BY id ASC
        """
    )
    n = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for row in cur:
            conf = row["behavior_confidence"]
            if args.require_confidence and conf is None:
                continue
            rec = {
                "video_id": int(row["id"]),
                "video_path": row["video_path"],
                "processor_version": row["processor_version"],
                "behavior_label": str(row["behavior_label"]).strip().lower(),
                "behavior_confidence": float(conf) if conf is not None else None,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    conn.close()
    print(json.dumps({"ok": True, "rows": n, "out": str(out_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
