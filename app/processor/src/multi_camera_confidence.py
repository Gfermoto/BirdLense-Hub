"""Boost detection confidence when Frigate reports the same species from multiple cameras (#153)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _parse_groups(raw: Any) -> list[frozenset[str]]:
    groups: list[frozenset[str]] = []
    if not raw or not isinstance(raw, (list, tuple)):
        return groups
    for item in raw:
        if isinstance(item, (list, tuple)):
            ids = {str(x).strip() for x in item if x is not None and str(x).strip()}
            if len(ids) >= 2:
                groups.append(frozenset(ids))
    return groups


def apply_multi_camera_confidence_boost(
    detections: list[dict],
    mqtt_events: list[dict],
    app_config,
) -> list[dict]:
    """If two+ cameras in the same configured group report the same species (Frigate), add boost.

    Config:
      processor.multi_camera_groups: groups of hub camera ids (same as Video → Cameras),
        e.g. [["cam_a","cam_b"]]
      processor.multi_camera_confidence_boost: additive to confidence (default 0.05),
        capped at 1.0
    """
    groups = _parse_groups(app_config.get("processor.multi_camera_groups"))
    try:
        boost = float(app_config.get("processor.multi_camera_confidence_boost", 0.05))
    except (TypeError, ValueError):
        boost = 0.05
    if not groups or boost <= 0:
        return detections

    from species_normalizer import _extract_common_for_merge

    def canon(species: str) -> str:
        return _extract_common_for_merge(species or "") or (species or "").strip().lower()

    # species_key -> set of camera ids (frigate only)
    by_species: dict[str, set[str]] = {}
    for ev in mqtt_events or []:
        if (ev or {}).get("source") != "frigate":
            continue
        cam = str(ev.get("camera") or "").strip()
        if not cam:
            continue
        sp = ev.get("species") or ev.get("sub_label") or ev.get("label") or ""
        key = canon(str(sp))
        if not key:
            continue
        by_species.setdefault(key, set()).add(cam)

    boosted_keys: set[str] = set()
    support_counts: dict[str, int] = {}
    for key, cams in by_species.items():
        for g in groups:
            support = len(cams & g)
            if support >= 2:
                boosted_keys.add(key)
                support_counts[key] = max(support_counts.get(key, 0), support)
                break

    if not boosted_keys:
        return detections

    changed = 0
    for d in detections:
        sp = d.get("species_name") or d.get("species") or ""
        species_key = canon(str(sp))
        if species_key not in boosted_keys:
            continue
        d["_multi_camera_count"] = int(support_counts.get(species_key, 0))
        d["_multi_camera_support"] = True
        try:
            c = float(d.get("confidence") or 0)
        except (TypeError, ValueError):
            c = 0.0
        new_c = min(1.0, c + boost)
        if new_c > c:
            d["confidence"] = new_c
            changed += 1

    if changed:
        logger.info(
            "Multi-camera confidence boost: +%.3f on %d detection(s) (groups=%s)",
            boost,
            changed,
            [sorted(g) for g in groups],
        )
    return detections
