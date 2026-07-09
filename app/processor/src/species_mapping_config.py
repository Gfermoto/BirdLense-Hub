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
    out: list[str] = []
    for word in clean.split():
        if "-" in word:
            out.append("-".join(seg.capitalize() for seg in word.split("-") if seg))
        else:
            out.append(word.capitalize())
    return " ".join(out)


def _birder_eu_label_mapping(app_config: Any) -> dict[str, str]:
    engine = str(app_config.get("processor.classifier_engine", "birder_eu") or "birder_eu").strip().lower()
    if engine not in ("birder", "birder_eu", "birder-eu", "eu-common", "eu_common"):
        return {}
    from inference.classifier_model_layout import birder_variant_name, resolve_birder_bundle_dir

    processor_root = Path(__file__).resolve().parents[1]
    variant = birder_variant_name(app_config)
    cls_root = processor_root / "models/classification"
    cfg_ref = app_config.get("processor.models.classifier") or app_config.get(
        "processor.models.classifier_birder_eu"
    )
    ref: Path | None = None
    if cfg_ref:
        p = Path(str(cfg_ref))
        if p.is_dir():
            ref = p
        elif p.suffix in (".pt", ".onnx"):
            ref = p.parent
    base = resolve_birder_bundle_dir(cls_root, variant, ref)
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
    return merged
