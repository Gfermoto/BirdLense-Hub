#!/usr/bin/env python3
"""Deep catalog polish: reconcile display names + repair card metadata.

Run inside birdlense container:
  PYTHONPATH=/app:/app/web:/app/processor/src python3 /app/scripts/catalog_deep_polish.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Container layout: /app = app/, scripts copied to /app/scripts/
_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
_WEB_ROOT = os.path.join(_APP_ROOT, "web")
_PROCESSOR_SRC = os.path.join(_APP_ROOT, "processor", "src")
if os.path.isdir(_WEB_ROOT):
    for p in (_WEB_ROOT, _APP_ROOT, _PROCESSOR_SRC):
        if p not in sys.path:
            sys.path.insert(0, p)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep catalog polish")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Create Species rows for every allowlist class (707+Rodent) before reconcile",
    )
    parser.add_argument("--materialize-limit", type=int, default=8000)
    parser.add_argument(
        "--skip-repair",
        action="store_true",
        help="Skip metadata repair (avoids sqlite locked while hub is writing)",
    )
    parser.add_argument("--rename-limit", type=int, default=6000)
    parser.add_argument("--repair-limit", type=int, default=6000)
    parser.add_argument("--duplicate-limit", type=int, default=500)
    args = parser.parse_args()

    from app import create_app
    from app_config.app_config import app_config

    app = create_app()
    with app.app_context():
        from services.species_catalog.registry import (
            catalog_cards_coverage_snapshot,
            ensure_allowlist_species_materialized,
            repair_catalog_cards,
        )
        from services.species_catalog_reconcile_service import deep_reconcile_species_catalog

        materialize_out = None
        if args.materialize:
            materialize_out = ensure_allowlist_species_materialized(
                app_config.get,
                fill_metadata=False,
                dry_run=bool(args.dry_run),
                limit=int(args.materialize_limit),
            )

        before = catalog_cards_coverage_snapshot(app_config.get)
        out = deep_reconcile_species_catalog(
            dry_run=bool(args.dry_run),
            rename_limit=int(args.rename_limit),
            duplicate_group_limit=int(args.duplicate_limit),
            app_config_get=app_config.get,
        )
        repair = None
        if not args.skip_repair:
            repair = repair_catalog_cards(
                app_config.get,
                dry_run=bool(args.dry_run),
                limit=int(args.repair_limit),
                priority_rotate=0,
            )
        after = catalog_cards_coverage_snapshot(app_config.get)
        payload = {
            "dry_run": bool(args.dry_run),
            "materialize": materialize_out,
            "before": before,
            "deep_reconcile": out,
            "repair": repair,
            "after": after,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
