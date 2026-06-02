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


def _birder_eu_label_mapping(app_config: Any) -> dict[str, str]:
    engine = str(app_config.get("processor.classifier_engine", "birder_eu") or "birder_eu").strip().lower()
    if engine not in ("birder", "birder_eu", "birder-eu", "eu-common", "eu_common"):
        return {}
    from inference.classifier_model_layout import birder_variant_name, classifier_openvino_rel_dir

    processor_root = Path(__file__).resolve().parents[1]
    variant = birder_variant_name(app_config)
    rel = (
        app_config.get("processor.models.classifier_openvino")
        or app_config.get("processor.models.classifier_birder_eu_openvino")
        or classifier_openvino_rel_dir(variant)
    )
    base = Path(rel) if os.path.isabs(str(rel)) else processor_root / str(rel)
    labels_path = base / "class_labels.txt"
    if not labels_path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        canon = _title_case_label(raw)
        out[raw] = canon
        if _norm_merge_key(raw) != _norm_merge_key(canon):
            out[canon] = canon
    return out


def _efficientnet_id2label_mapping(app_config: Any) -> dict[str, str]:
    engine = str(app_config.get("processor.classifier_engine", "efficientnet_b2") or "efficientnet_b2").strip().lower()
    if engine != "efficientnet_b2":
        return {}
    rel = (
        app_config.get(
            "processor.models.classifier_efficientnet_b2",
            "models/classification/weights/efficientnet_b2_global",
        )
        or "models/classification/weights/efficientnet_b2_global"
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
    for variant, canonical in _birder_eu_label_mapping(app_config).items():
        merged.setdefault(variant, canonical)
    for variant, canonical in _efficientnet_id2label_mapping(app_config).items():
        merged.setdefault(variant, canonical)
    return merged
