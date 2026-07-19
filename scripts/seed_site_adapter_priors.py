#!/usr/bin/env python3
"""Seed site_adapter species_priors from feedback relabels (+ optional video DB).

Dry-run by default. Writes ``data/site_adapter/manifest.json`` when ``--apply``.

Example (Orin)::

  python3 scripts/seed_site_adapter_priors.py \\
    --db app/data/db/birdlense.db --data-dir app/data --from-video-species

  python3 scripts/seed_site_adapter_priors.py \\
    --db app/data/db/birdlense.db --data-dir app/data \\
    --apply --status canary --canary-share 0.25 --delta 0.04
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GENERIC = {"bird", "unknown", "unknown bird", "птица", "background", "none", "null"}


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def _priors_from_relabels(
    con: sqlite3.Connection,
    *,
    min_count: int,
    delta: float,
    max_species: int,
) -> dict[str, float]:
    try:
        rows = con.execute(
            """
            SELECT trim(to_species_name) AS name, COUNT(*) AS n
            FROM detection_feedback_event
            WHERE action = 'relabel'
              AND to_species_name IS NOT NULL
              AND TRIM(to_species_name) != ''
            GROUP BY lower(trim(to_species_name))
            ORDER BY n DESC
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"WARN: relabel query: {exc}", file=sys.stderr)
        return {}

    priors: dict[str, float] = {}
    for row in rows:
        name = str(row["name"] or "").strip()
        n = int(row["n"] or 0)
        if not name or name.lower() in GENERIC or n < min_count:
            continue
        priors[name] = round(min(0.12, max(0.01, float(delta))), 4)
        if len(priors) >= max_species:
            break
    return priors


def _priors_from_video_species(
    con: sqlite3.Connection,
    *,
    min_count: int,
    delta: float,
    max_species: int,
    conf_min: float,
) -> dict[str, float]:
    """Weaker priors from frequent high-conf Hub YOLO named visits (pack helpers)."""
    try:
        rows = con.execute(
            """
            SELECT s.name AS name, COUNT(*) AS n
            FROM video_species vs
            JOIN species s ON s.id = vs.species_id
            JOIN video v ON v.id = vs.video_id
            WHERE v.deleted_at IS NULL
              AND lower(coalesce(vs.detection_provider, '')) LIKE '%yolo%'
              AND coalesce(vs.classifier_needs_review, 0) = 0
              AND vs.confidence >= ?
              AND lower(s.name) NOT IN ('bird','unknown','unknown bird','птица')
            GROUP BY lower(s.name)
            ORDER BY n DESC
            """,
            (float(conf_min),),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"WARN: video_species query: {exc}", file=sys.stderr)
        return {}

    priors: dict[str, float] = {}
    soft = round(min(0.08, max(0.01, float(delta) * 0.75)), 4)
    for row in rows:
        name = str(row["name"] or "").strip()
        n = int(row["n"] or 0)
        if not name or name.lower() in GENERIC or n < min_count:
            continue
        priors[name] = soft
        if len(priors) >= max_species:
            break
    return priors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--min-count", type=int, default=2)
    ap.add_argument("--delta", type=float, default=0.04)
    ap.add_argument("--max-species", type=int, default=12)
    ap.add_argument("--from-video-species", action="store_true")
    ap.add_argument("--video-conf-min", type=float, default=0.50)
    ap.add_argument("--status", default="canary", choices=("inactive", "canary", "active"))
    ap.add_argument("--canary-share", type=float, default=0.25)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not args.db.is_file():
        print(f"FAIL: db missing {args.db}", file=sys.stderr)
        return 1

    data_dir = args.data_dir
    if data_dir is None:
        data_dir = args.db.parent.parent if args.db.parent.name == "db" else args.db.parent

    con = _connect(args.db)
    try:
        priors = _priors_from_relabels(
            con,
            min_count=args.min_count,
            delta=args.delta,
            max_species=args.max_species,
        )
        if args.from_video_species:
            video_priors = _priors_from_video_species(
                con,
                min_count=max(2, args.min_count),
                delta=args.delta,
                max_species=args.max_species,
                conf_min=args.video_conf_min,
            )
            # Relabel wins on conflict (stronger evidence).
            merged = dict(video_priors)
            merged.update(priors)
            priors = merged
    finally:
        con.close()

    if not priors:
        print(
            "FAIL: no priors (need relabels and/or --from-video-species)",
            file=sys.stderr,
        )
        return 1

    print(f"priors ({len(priors)}):")
    for name, delta in sorted(priors.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        print(f"  {name}: +{delta}")

    if not args.apply:
        print("dry-run: not writing manifest (pass --apply)")
        return 0

    sys.path.insert(0, str(REPO / "app" / "processor" / "src"))
    from site_adapter import write_site_adapter_manifest

    source_bits = ["relabel"]
    if args.from_video_species:
        source_bits.append("video_species")
    manifest = write_site_adapter_manifest(
        data_dir,
        version=f"priors-{'-'.join(source_bits)}-{len(priors)}",
        source="seed_site_adapter_priors.py",
        status=args.status,
        notes="Seeded priors; review before raising canary_share / active.",
        canary_share=args.canary_share,
        species_priors=priors,
    )
    print(f"OK wrote {data_dir / 'site_adapter' / 'manifest.json'} status={manifest.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
