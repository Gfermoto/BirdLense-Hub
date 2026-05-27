#!/usr/bin/env python3
"""Refresh metadata for allowlist species missing image and/or real description (UI button, batch)."""

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=6000)
    args = parser.parse_args()

    from app import create_app
    from app_config.app_config import app_config
    from models import Species, db
    from services.species_catalog.registry import (
        _catalog_description_is_placeholder,
        catalog_cards_coverage_snapshot,
        load_catalog_allowlist_names,
        species_name_match_norm_keys,
    )
    from species_metadata import refresh_species_metadata_from_sources

    app = create_app()
    with app.app_context():
        before = catalog_cards_coverage_snapshot(app_config.get)
        names = list(load_catalog_allowlist_names(app_config.get) or ())
        by_norm: dict[str, Species] = {}
        for sp in Species.query.all():
            for k in species_name_match_norm_keys(sp.name or ""):
                by_norm.setdefault(k, sp)

        targets: list[Species] = []
        for aname in names:
            for k in species_name_match_norm_keys(aname):
                sp = by_norm.get(k)
                if sp:
                    targets.append(sp)
                    break
        uniq: dict[int, Species] = {int(sp.id): sp for sp in targets}
        def _needs_refresh(sp: Species) -> bool:
            if not (sp.image_url or "").strip():
                return True
            desc = (sp.description or "").strip()
            return not desc or _catalog_description_is_placeholder(desc)

        missing = [sp for sp in uniq.values() if _needs_refresh(sp)][
            : max(1, int(args.limit))
        ]

        fixed = 0
        for sp in missing:
            if args.dry_run:
                continue
            refresh_species_metadata_from_sources(sp)
            desc = (sp.description or "").strip()
            if (sp.image_url or "").strip() and desc and not _catalog_description_is_placeholder(desc):
                fixed += 1

        if args.dry_run:
            db.session.rollback()
        else:
            db.session.commit()
            from services.species_catalog.registry import _invalidate_species_catalog_http_caches

            _invalidate_species_catalog_http_caches()

        after = catalog_cards_coverage_snapshot(app_config.get)
        print(
            json.dumps(
                {
                    "dry_run": bool(args.dry_run),
                    "missing_before": len(missing),
                    "images_fixed": fixed,
                    "before": before,
                    "after": after,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
