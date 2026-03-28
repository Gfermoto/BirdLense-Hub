"""Merge species_confidence_overrides with eBird regional top (#128)."""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)


def _ensure_web_on_path() -> None:
    """Ensure /app/web on sys.path (entrypoint sets PYTHONPATH; tests may not)."""
    root = os.environ.get('BIRDLENSE_APP_ROOT', '/app')
    web = os.path.join(root, 'web')
    if os.path.isdir(web) and web not in sys.path:
        sys.path.insert(0, web)


def merge_species_confidence_overrides_with_ebird_top(app_config) -> dict[str, float]:
    """Return effective per-species classifier thresholds.

    Manual entries in ``processor.species_confidence_overrides`` always win.
    When ``processor.ebird_regional_top_auto_confidence`` is true and
    ``secrets.ebird_api_key`` is set, adds lower thresholds for BirdLense names
    in the regional eBird top (after ``ebird.species_mapping``).

    Auto threshold = max(floor, min_confidence_to_process - delta), clamped to
    (0.01, 0.99).
    """
    raw_manual = app_config.get('processor.species_confidence_overrides') or {}
    manual: dict[str, float] = {}
    if isinstance(raw_manual, dict):
        for k, v in raw_manual.items():
            if k is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if 0.0 <= fv <= 1.0:
                manual[str(k).strip()] = fv

    auto = app_config.get('processor.ebird_regional_top_auto_confidence', True)
    if not auto:
        return manual

    api_key = (app_config.get('secrets.ebird_api_key') or '').strip()
    if not api_key:
        return manual

    try:
        base = float(
            app_config.get('processor.min_confidence_to_process', 0.3)
        )
    except (TypeError, ValueError):
        base = 0.3
    try:
        delta = float(
            app_config.get(
                'processor.ebird_regional_top_confidence_delta', 0.05
            )
        )
    except (TypeError, ValueError):
        delta = 0.05
    try:
        floor_v = float(
            app_config.get(
                'processor.ebird_regional_top_confidence_floor', 0.05
            )
        )
    except (TypeError, ValueError):
        floor_v = 0.05

    delta = max(0.0, min(delta, 0.5))
    base = max(0.01, min(base, 0.99))
    floor_v = max(0.01, min(floor_v, base))
    auto_val = max(floor_v, base - delta)
    auto_val = max(0.01, min(auto_val, 0.99))

    _ensure_web_on_path()
    try:
        from services.ebird_region_service import (
            _build_region_code,
            ebird_common_to_birdlense_name,
            get_region_top_species_cached,
        )
    except ImportError as e:
        logger.warning(
            'eBird regional auto-confidence: import failed: %s', e
        )
        return manual

    region = _build_region_code()
    try:
        top = get_region_top_species_cached(api_key, region)
    except Exception as e:
        logger.warning(
            'eBird regional auto-confidence: top list failed: %s', e
        )
        return manual

    if not top:
        return manual

    out = dict(manual)
    added = 0
    for raw in top:
        ebird = (raw or '').strip()
        if not ebird:
            continue
        bl = (ebird_common_to_birdlense_name(ebird) or '').strip()
        if not bl:
            continue
        if bl in out:
            continue
        out[bl] = auto_val
        added += 1

    if added:
        logger.info(
            'eBird regional auto-confidence: region=%s +%d species @ %.3f '
            '(base=%.3f delta=%.3f floor=%.3f; manual keys preserved)',
            region,
            added,
            auto_val,
            base,
            delta,
            floor_v,
        )
    return out
