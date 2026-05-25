"""Shared species mapping resolver for processor runtime.

Merges detector/classifier and external checklist aliases into one lookup map.
"""

from __future__ import annotations

from typing import Any


def build_species_mapping(app_config: Any) -> dict:
    detection_map = app_config.get("detection.species_mapping") or {}
    ebird_map = app_config.get("ebird.species_mapping") or {}
    if not isinstance(detection_map, dict):
        detection_map = {}
    if not isinstance(ebird_map, dict):
        ebird_map = {}
    return {**detection_map, **ebird_map}

