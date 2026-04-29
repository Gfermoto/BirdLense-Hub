#!/usr/bin/env python3
"""Export decision_trace JSON payloads from Hub SQLite (activity_log).

Does not require Flask. Example::

  python3 scripts/export_decision_traces_sqlite.py --db app/data/db/birdlense.db --limit 20 \\
    --out-dir /tmp/traces
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db",
        default=os.environ.get("BIRDLENSE_SQLITE", ""),
        help="Path to birdlense.db (default: env BIRDLENSE_SQLITE)",
    )
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--since-id", type=int, default=0)
    ap.add_argument("--out-dir", required=True, help="Write one JSON file per row: trace_<id>.json")
    args = ap.parse_args()
    db_path = (args.db or "").strip()
    if not db_path:
        print("Set --db or BIRDLENSE_SQLITE", file=sys.stderr)
        return 2
    if not os.path.isfile(db_path):
        print(f"SQLite file not found: {db_path}", file=sys.stderr)
        return 2
    os.makedirs(args.out_dir, exist_ok=True)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            """
            SELECT id, created_at, data
            FROM activity_log
            WHERE type = 'decision_trace' AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (int(args.since_id), int(args.limit)),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    n = 0
    for row_id, created_at, data in rows:
        out_path = os.path.join(args.out_dir, f"trace_{row_id}.json")
        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError:
            parsed = {"parse_error": True, "raw": (data or "")[:500]}
        envelope = {
            "activity_log_id": row_id,
            "created_at": created_at,
            "payload": parsed,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, indent=2)
        n += 1
    print(json.dumps({"written": n, "out_dir": os.path.abspath(args.out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
