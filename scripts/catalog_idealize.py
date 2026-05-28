#!/usr/bin/env python3
"""Идеализация каталога: 707+Rodent, без legacy/off-allowlist мусора.

Контейнер:
  PYTHONPATH=/app:/app/web:/app/processor/src python3 /app/scripts/catalog_idealize.py --audit
  PYTHONPATH=/app:/app/web:/app/processor/src python3 /app/scripts/catalog_idealize.py --apply

Рекомендуется остановить hub на время --apply (sqlite lock):
  docker compose stop birdlense && … --apply && docker compose start birdlense
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
_WEB_ROOT = os.path.join(_APP_ROOT, "web")
_PROCESSOR_SRC = os.path.join(_APP_ROOT, "processor", "src")
for p in (_WEB_ROOT, _APP_ROOT, _PROCESSOR_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    parser = argparse.ArgumentParser(description="Idealize species catalog (Birder 707 + Rodent)")
    parser.add_argument("--audit", action="store_true", help="Only audit counts")
    parser.add_argument("--apply", action="store_true", help="Run full idealize (not dry-run)")
    parser.add_argument(
        "--keep-active-off-allowlist",
        action="store_true",
        help="Do not merge active off-allowlist species into Unknown",
    )
    args = parser.parse_args()
    dry_run = not args.apply

    from app import create_app
    from app_config.app_config import app_config
    from services.species_catalog.allowlist import clear_allowlist_cache
    from services.species_catalog.idealize import audit_species_catalog, idealize_species_catalog

    app = create_app()
    with app.app_context():
        if args.audit and not args.apply:
            payload = {"audit": audit_species_catalog(app_config.get)}
        else:
            payload = idealize_species_catalog(
                dry_run=dry_run,
                reassign_active_off_allowlist=not args.keep_active_off_allowlist,
                app_config_get=app_config.get,
            )
        if args.apply:
            clear_allowlist_cache()
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
