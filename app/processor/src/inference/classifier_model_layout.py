"""Classifier weights layout — mirrors ``detection/weights/trapper_ai_v02_2024.*``."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def birder_variant_name(app_config: Mapping[str, Any] | None) -> str:
    from inference.birder_eu_classifier import default_birder_variant

    return default_birder_variant(app_config)


def classifier_torch_rel_pt(variant: str) -> str:
    return f"models/classification/weights/{variant}.pt"


def resolve_birder_bundle_dir(weights_root: Path, variant: str, ref: Path | None = None) -> Path:
    """Bundle dir with ``class_labels.txt``."""
    if ref is not None and ref.is_dir():
        return ref
    return weights_root / variant


def resolve_birder_pt_path(weights_root: Path, variant: str, ref: Path | None = None) -> Path:
    if ref is not None and ref.is_file() and ref.suffix == ".pt":
        return ref
    return weights_root / f"{variant}.pt"
