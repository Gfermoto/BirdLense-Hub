"""Classifier weights layout — ``models/classification/{variant}/`` (без промежуточного ``weights/``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def birder_variant_name(app_config: Mapping[str, Any] | None) -> str:
    from inference.birder_eu_classifier import default_birder_variant

    return default_birder_variant(app_config)


def classification_root_rel() -> str:
    return "models/classification"


def classifier_model_dir_rel(variant: str) -> str:
    return f"models/classification/{variant}"


def classifier_torch_rel_pt(variant: str) -> str:
    return f"{classifier_model_dir_rel(variant)}/{variant}.pt"


def classifier_onnx_rel(variant: str) -> str:
    return f"{classifier_model_dir_rel(variant)}/{variant}.onnx"


def resolve_birder_model_dir(classification_root: Path, variant: str) -> Path:
    return classification_root / variant


def resolve_birder_onnx_path(model_dir: Path, variant: str, ref: Path | None = None) -> Path:
    if ref is not None and ref.is_file() and ref.suffix == ".onnx":
        return ref
    return model_dir / f"{variant}.onnx"


def resolve_birder_bundle_dir(classification_root: Path, variant: str, ref: Path | None = None) -> Path:
    """Bundle dir with ``class_labels.txt`` — same as model dir."""
    if ref is not None and ref.is_dir():
        return ref
    if ref is not None and ref.is_file():
        return ref.parent
    return classification_root / variant


def resolve_birder_pt_path(model_dir: Path, variant: str, ref: Path | None = None) -> Path:
    if ref is not None and ref.is_file() and ref.suffix == ".pt":
        return ref
    return model_dir / f"{variant}.pt"
