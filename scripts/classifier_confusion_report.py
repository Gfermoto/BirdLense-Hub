#!/usr/bin/env python3
"""Classifier confusion + threshold hints from operator corrections (SOTA-16 / #507).

Usage (repo root):
  make classifier-confusion-report
  python scripts/classifier_confusion_report.py --db app/data/db/birdlense.db --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_WEB = _REPO / "app" / "web"
for p in (_WEB,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from services.classifier_calibration_report import build_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Classifier confusion from species_correction log")
    parser.add_argument("--db", type=Path, default=Path("app/data/db/birdlense.db"))
    parser.add_argument("--limit", type=int, default=15, help="Top-N confusion pairs")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()
    db_path = args.db.expanduser().resolve()
    if not db_path.is_file():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    report = build_report(db_path, pair_limit=max(1, args.limit))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"Corrections analyzed: {report['corrections_analyzed']}")
    print(f"\nTop {args.limit} confusion pairs (from → to):")
    for row in report.get("top_confusion_pairs") or []:
        print(f"  {row['count']:4d}  {row['from']}  →  {row['to']}")

    rec = report.get("threshold_recommendations") or {}
    yaml_rec = rec.get("recommended_processor_yaml") or {}
    if yaml_rec:
        print("\nSuggested processor YAML (review before apply):")
        for key, val in sorted(yaml_rec.items()):
            print(f"  {key}: {val}")
    if rec.get("bird_skip_classifier_doc"):
        print(f"\nbird_skip_classifier_max_area_frac: {rec['bird_skip_classifier_doc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
