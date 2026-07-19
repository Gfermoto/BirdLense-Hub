#!/usr/bin/env python3
"""Seed site_adapter species_priors from DetectionFeedbackEvent relabels (RC5).

Dry-run by default. Writes ``data/site_adapter/manifest.json`` when ``--apply``.

Example (Orin)::

  python3 scripts/seed_site_adapter_priors.py \\
    --db app/data/db/birdlense.db --data-dir app/data --dry-run

  python3 scripts/seed_site_adapter_priors.py \\
    --db app/data/db/birdlense.db --data-dir app/data \\
    --apply --status canary --canary-share 0.25 --delta 0.04
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GENERIC = {"bird", "unknown", "unknown bird", "птица", "background", "none", "null"}


def _priors_from_relabels(
    db_path: Path,
    *,
    min_count: int,
    delta: float,
    max_species: int,
) -> dict[str, float]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT to_species_name AS name, COUNT(*) AS n
            FROM detection_feedback_event
            WHERE action = 'relabel'
              AND to_species_name IS NOT NULL
              AND TRIM(to_species_name) != ''
            GROUP BY lower(trim(to_species_name))
            ORDER BY n DESC
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return {}
    finally:
        con.close()

    counts: Counter[str] = Counter()
    for row in rows:
        name = str(row["name"] or "").strip()
        key = name.lower()
        if not name or key in GENERIC:
            continue
        counts[name] += int(row["n"] or 0)

    priors: dict[str, float] = {}
    for name, n in counts.most_common(max(1, max_species)):
        if n < min_count:
            continue
        # Cap delta so canary cannot force absurd accepts.
        priors[name] = round(min(0.12, max(0.01, float(delta))), 4)
    return priors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--delta", type=float, default=0.04)
    ap.add_argument("--max-species", type=int, default=12)
    ap.add_argument("--status", default="canary", choices=("inactive", "canary", "active"))
    ap.add_argument("--canary-share", type=float, default=0.25)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()
    if args.apply:
        args.dry_run = False

    if not args.db.is_file():
        print(f"FAIL: db missing {args.db}", file=sys.stderr)
        return 1

    data_dir = args.data_dir
    if data_dir is None:
        data_dir = args.db.parent.parent if args.db.parent.name == "db" else args.db.parent

    priors = _priors_from_relabels(
        args.db,
        min_count=args.min_count,
        delta=args.delta,
        max_species=args.max_species,
    )
    if not priors:
        print("FAIL: no relabel priors (need more DetectionFeedbackEvent relabels)", file=sys.stderr)
        return 1

    print(f"priors ({len(priors)}):")
    for name, delta in sorted(priors.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        print(f"  {name}: +{delta}")

    if args.dry_run:
        print("dry-run: not writing manifest (pass --apply)")
        return 0

    sys.path.insert(0, str(REPO / "app" / "processor" / "src"))
    from site_adapter import write_site_adapter_manifest

    manifest = write_site_adapter_manifest(
        data_dir,
        version=f"priors-relabel-{len(priors)}",
        source="seed_site_adapter_priors.py",
        status=args.status,
        notes="Seeded from DetectionFeedbackEvent relabel counts; review before active.",
        canary_share=args.canary_share,
        species_priors=priors,
    )
    print(f"OK wrote {data_dir / 'site_adapter' / 'manifest.json'} status={manifest.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
