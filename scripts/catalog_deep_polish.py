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
            repair_catalog_cards,
        )
        from services.species_catalog_reconcile_service import deep_reconcile_species_catalog

        before = catalog_cards_coverage_snapshot(app_config.get)
        out = deep_reconcile_species_catalog(
            dry_run=bool(args.dry_run),
            rename_limit=int(args.rename_limit),
            duplicate_group_limit=int(args.duplicate_limit),
            app_config_get=app_config.get,
        )
        repair = repair_catalog_cards(
            app_config.get,
            dry_run=bool(args.dry_run),
            limit=int(args.repair_limit),
            priority_rotate=0,
        )
        after = catalog_cards_coverage_snapshot(app_config.get)
        payload = {
            "dry_run": bool(args.dry_run),
            "before": before,
            "deep_reconcile": out,
            "repair": repair,
            "after": after,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
