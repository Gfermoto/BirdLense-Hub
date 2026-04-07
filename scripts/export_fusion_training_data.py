#!/usr/bin/env python3
\"\"\"Export training data for fusion scorer.

Usage:
  - From CSV (recommended): you can point this script at an existing CSV of
    corrections/features: --source-csv path/to/corrections_features.csv
  - From DB (best-effort): run inside project with DB available:
      python3 scripts/export_fusion_training_data.py --out out.csv --source db

Output: CSV with columns:
    detector_conf,classifer_conf,birdnet_prior,key_frame_score,key_frame_count,
    multi_camera_count,label

Label: 1 = accepted/true detection, 0 = rejected/false
\"\"\"
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable


DEFAULT_COLUMNS = [
    "detector_conf",
    "classifier_conf",
    "birdnet_prior",
    "key_frame_score",
    "key_frame_count",
    "multi_camera_count",
    "label",
]


def export_from_csv(src: Path, out: Path) -> None:
    # copy or normalize columns
    with src.open("r", encoding="utf-8") as fsrc, out.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fsrc)
        writer = csv.DictWriter(fout, fieldnames=DEFAULT_COLUMNS)
        writer.writeheader()
        for row in reader:
            out_row = {k: row.get(k, 0) for k in DEFAULT_COLUMNS}
            writer.writerow(out_row)
    print(f"Wrote normalized CSV to {out}")


def export_from_db(out: Path) -> None:
    \"\"\"Best-effort exporter that tries to read VideoSpecies or Decision rows.
    If schema differs, print guidance and exit non-zero.\"\"\"
    try:
        # app context expected; attempt to import SQLAlchemy models
        sys.path.insert(0, str(Path.cwd()))
        from models import db, VideoSpecies  # type: ignore
    except Exception as e:
        print("DB export failed: cannot import models. Run this inside project with DB available.", file=sys.stderr)
        print("Error:", e, file=sys.stderr)
        sys.exit(2)

    rows = (
        db.session.query(VideoSpecies)
        .filter(VideoSpecies.source == "video")
        .with_entities(
            VideoSpecies.id,
            VideoSpecies.video_id,
            VideoSpecies.track_id,
            VideoSpecies.confidence,
            VideoSpecies.extra,  # optional JSON with diagnostic fields
        )
        .all()
    )
    if not rows:
        print("No rows found in VideoSpecies. Nothing exported.", file=sys.stderr)
        sys.exit(3)

    with out.open("w", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=DEFAULT_COLUMNS)
        writer.writeheader()
        for r in rows:
            extra = getattr(r, "extra", {}) or {}
            writer.writerow(
                {
                    "detector_conf": extra.get("detector_confidence") or 0.0,
                    "classifier_conf": extra.get("classifier_confidence") or getattr(r, "confidence", 0.0),
                    "birdnet_prior": extra.get("_birdnet_prior") or 0.0,
                    "key_frame_score": extra.get("best_frame_score") or 0.0,
                    "key_frame_count": extra.get("key_frame_count") or 0,
                    "multi_camera_count": extra.get("_multi_camera_count") or 0,
                    # Label: infer from a trusted flag in extra (accepted=true/false)
                    "label": 1 if extra.get("accepted") else 0,
                }
            )
    print(f"Exported {out} from DB (best-effort). Verify columns and labels before training.")


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", "-o", type=Path, required=True, help="Output CSV path")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--source-csv", type=Path, help="Normalize existing CSV of features")
    grp.add_argument("--source", choices=["db"], help="Source 'db' to try export from DB")
    args = p.parse_args(list(argv) if argv else None)

    out = args.out
    if args.source_csv:
        export_from_csv(args.source_csv, out)
        return 0
    if args.source == "db":
        export_from_db(out)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

