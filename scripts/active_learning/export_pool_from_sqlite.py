#!/usr/bin/env python3
"""Export active-learning pool JSONL directly from Hub SQLite (#369).

Reads ``activity_log`` rows of type ``decision_trace`` without importing Flask.
This closes the loop for operator runs: DB -> pool manifest, no manual DB
surgery. Crop files are still exported separately; entries use ``_pending`` paths.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from decision_trace_to_pool_manifest import _iter_rows, _maybe_float, row_to_entry


def _load_trace_payload(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _iter_trace_rows(conn: sqlite3.Connection, since_id: int, limit: int):
    cur = conn.execute(
        """
        SELECT id, created_at, data
        FROM activity_log
        WHERE type = 'decision_trace' AND id > ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (int(since_id), int(limit)),
    )
    yield from cur.fetchall()


def _should_keep(row: dict, args) -> bool:
    if args.needs_review_only and not bool(row.get("classifier_needs_review")):
        return False
    ent = _maybe_float(row.get("classifier_entropy"))
    margin = _maybe_float(row.get("classifier_top1_top2_margin"))
    if args.entropy_ge is not None and (ent is None or ent < args.entropy_ge):
        return False
    if args.margin_le is not None and (margin is None or margin > args.margin_le):
        return False
    return True


def export_pool_from_sqlite(args) -> int:
    db_path = (args.db or "").strip()
    if not db_path:
        print("Set --db or BIRDLENSE_SQLITE", file=sys.stderr)
        return 2
    if not os.path.isfile(db_path):
        print(f"SQLite file not found: {db_path}", file=sys.stderr)
        return 2
    seen: set[tuple[str, int]] = set()
    written = 0
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        out_fh = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
        try:
            for _row_id, _created_at, raw_data in _iter_trace_rows(conn, args.since_id, args.limit):
                payload = _load_trace_payload(raw_data)
                if not payload:
                    continue
                video_id = str(payload.get("video_id") or args.video_id or "unknown_video")
                for trace_row in _iter_rows(payload):
                    if not _should_keep(trace_row, args):
                        continue
                    entry = row_to_entry(
                        trace_row,
                        video_id,
                        seed=int(args.seed),
                        model_version=str(args.model_version),
                    )
                    if entry is None:
                        continue
                    key = (entry["video_id"], int(entry["track_id"]))
                    if args.dedupe and key in seen:
                        continue
                    seen.add(key)
                    out_fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    written += 1
        finally:
            if out_fh is not sys.stdout:
                out_fh.close()
    finally:
        conn.close()
    print(json.dumps({"rows_written": written}, ensure_ascii=False), file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.environ.get("BIRDLENSE_SQLITE", ""))
    ap.add_argument("--output", "-o", default="", help="Output JSONL (default stdout)")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--since-id", type=int, default=0)
    ap.add_argument("--video-id", default=None, help="Fallback video_id when trace lacks one")
    ap.add_argument("--needs-review-only", action="store_true")
    ap.add_argument("--entropy-ge", type=float, default=None)
    ap.add_argument("--margin-le", type=float, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model-version", default="pipeline_unknown")
    ap.add_argument("--dedupe", action="store_true", default=True)
    args = ap.parse_args()
    return export_pool_from_sqlite(args)


if __name__ == "__main__":
    raise SystemExit(main())
