"""Heuristic lines for ebird.species_mapping from regional eBird top vs catalog."""

from __future__ import annotations

import difflib
from typing import Any

from app_config.app_config import app_config

from models import Species, db
from services.ebird_region_service import (
    _build_region_code,
    ebird_common_to_birdlense_name,
    get_region_top_species_cached,
)

_FUZZY_CUTOFF = 0.82


def _species_names_and_lower_map() -> tuple[list[str], dict[str, str]]:
    rows = db.session.query(Species.name).order_by(Species.name).all()
    names = [r[0] for r in rows if r and r[0]]
    lower_to_canon = {n.lower(): n for n in names}
    return names, lower_to_canon


def _species_row_for_exact(name: str):
    if not name or not name.strip():
        return None
    stripped = name.strip()
    return db.session.query(Species.id).filter_by(name=stripped).first()


def build_ebird_mapping_suggestions(max_items: int = 40) -> dict[str, Any]:
    """Regional top names that do not resolve to a Species after current mapping.

    Each suggestion has kind: case_variant, fuzzy, or unmatched.
    """
    api_key = (app_config.get("secrets.ebird_api_key") or "").strip()
    region_code = _build_region_code()
    if not api_key:
        return {
            "region_code": region_code,
            "ebird_api_configured": False,
            "top_count": 0,
            "suggestions": [],
        }

    top = get_region_top_species_cached(api_key, region_code)
    names, lower_to_canon = _species_names_and_lower_map()
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in top:
        ebird = (raw or "").strip()
        if not ebird or ebird in seen:
            continue
        seen.add(ebird)

        mapped = ebird_common_to_birdlense_name(ebird)
        if _species_row_for_exact(mapped):
            continue

        if mapped.lower() in lower_to_canon:
            canon = lower_to_canon[mapped.lower()]
            suggestions.append(
                {
                    "ebird_name": ebird,
                    "birdlense_name": canon,
                    "kind": "case_variant",
                    "score": 1.0,
                }
            )
        elif ebird.lower() in lower_to_canon and ebird.lower() != mapped.lower():
            canon = lower_to_canon[ebird.lower()]
            suggestions.append(
                {
                    "ebird_name": ebird,
                    "birdlense_name": canon,
                    "kind": "case_variant",
                    "score": 1.0,
                }
            )
        else:
            candidates = difflib.get_close_matches(mapped, names, n=3, cutoff=_FUZZY_CUTOFF)
            if not candidates:
                candidates = difflib.get_close_matches(ebird, names, n=3, cutoff=_FUZZY_CUTOFF)
            if candidates:
                best = candidates[0]
                score = difflib.SequenceMatcher(None, mapped.lower(), best.lower()).ratio()
                suggestions.append(
                    {
                        "ebird_name": ebird,
                        "birdlense_name": best,
                        "kind": "fuzzy",
                        "score": round(score, 3),
                    }
                )
            else:
                suggestions.append(
                    {
                        "ebird_name": ebird,
                        "birdlense_name": None,
                        "kind": "unmatched",
                        "score": None,
                    }
                )

        if len(suggestions) >= max_items:
            break

    return {
        "region_code": region_code,
        "ebird_api_configured": True,
        "top_count": len(top),
        "suggestions": suggestions,
    }
