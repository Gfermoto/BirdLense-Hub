#!/usr/bin/env python3
"""Export feedback-learning slices from operator corrections/deletions (#397)."""

from __future__ import annotations

import argparse
import json
import os
import sys


def _project_web_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(root, "app", "web")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="app/data/db/birdlense.db", help="Path to SQLite DB")
    parser.add_argument("--data-dir", default="app/data", help="BirdLense data dir (for dataset crops)")
    parser.add_argument(
        "--output-dir",
        default="app/data/feedback_exports",
        help="Where to write export folders and latest_status.json",
    )
    parser.add_argument("--since-hours", type=int, default=24, help="Lookback window")
    parser.add_argument("--limit", type=int, default=5000, help="Max feedback events")
    parser.add_argument("--dry-run", action="store_true", help="Do not copy files")
    parser.add_argument("--export-tag", default="", help="Stable export tag (deterministic folder name)")
    args = parser.parse_args()

    web_root = _project_web_root()
    if web_root not in sys.path:
        sys.path.insert(0, web_root)

    from services.feedback_loop_service import export_feedback_learning_dataset  # noqa: WPS433

    out = export_feedback_learning_dataset(
        db_path=args.db,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        since_hours=args.since_hours,
        limit=args.limit,
        dry_run=args.dry_run,
        export_tag=(args.export_tag or None),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
