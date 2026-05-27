"""Shared species mapping resolver for processor runtime.

Merges detector/classifier and external checklist aliases into one lookup map.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _norm_merge_key(name: str) -> str:
    return str(name or "").strip().lower().replace("_", " ").replace("-", " ")


def _title_case_label(label: str) -> str:
    clean = " ".join(str(label or "").strip().split())
    if not clean:
        return clean
    if clean.isupper():
        return clean.title()
    return clean


def _efficientnet_id2label_mapping(app_config: Any) -> dict[str, str]:
    engine = str(app_config.get("processor.classifier_engine", "efficientnet_b2") or "efficientnet_b2").strip().lower()
    if engine != "efficientnet_b2":
        return {}
    rel = (
        app_config.get(
            "processor.models.classifier_efficientnet_b2",
            "models/classification/weights/birds_classifier_efficientnetb2",
        )
        or "models/classification/weights/birds_classifier_efficientnetb2"
    )
    processor_root = Path(__file__).resolve().parents[1]
    base = Path(rel) if os.path.isabs(str(rel)) else processor_root / str(rel)
    cfg_path = base / "config.json"
    if not cfg_path.is_file():
        return {}
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for label in (raw.get("id2label") or {}).values():
        line = str(label or "").strip()
        if not line:
            continue
        canon = _title_case_label(line)
        out[line] = canon
        if _norm_merge_key(line) != _norm_merge_key(canon):
            out[canon] = canon
    return out


def build_species_mapping(app_config: Any) -> dict:
    detection_map = app_config.get("detection.species_mapping") or {}
    ebird_map = app_config.get("ebird.species_mapping") or {}
    if not isinstance(detection_map, dict):
        detection_map = {}
    if not isinstance(ebird_map, dict):
        ebird_map = {}
    merged: dict[str, str] = {**detection_map, **ebird_map}
    for variant, canonical in _efficientnet_id2label_mapping(app_config).items():
        merged.setdefault(variant, canonical)
    return merged

