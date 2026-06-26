"""Resolve classifier weight path.

Birder EU prod uses flat ``{variant}.pt`` + ONNX.
Jetson Ornimetrics uses region-selected ONNX species packs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


def classifier_engine(app_config: Mapping[str, Any]) -> str:
    """Resolve classifier engine alias."""
    raw = app_config.get("processor.classifier_engine")
    eng = str(raw).strip().lower() if raw is not None else "birder_eu"
    if eng in ("birder", "birder_eu", "birder-eu", "eu-common", "eu_common"):
        return "birder_eu"
    if eng in (
        "efficientnet",
        "efficientnet_b2",
        "hf_efficientnet_b2",
        "birds_efficientnet_b2",
        "chriamue",
        "bird_species_classifier",
        "bird-species-classifier",
        "ornimetrics",
        "ornimetrics_species",
    ):
        return "efficientnet_b2"
    return "yolo"


def classifier_weights_available(path: str) -> bool:
    if not path:
        return False
    if os.path.isfile(path):
        return path.endswith((".pt", ".onnx"))
    if os.path.isdir(path):
        try:
            names = os.listdir(path)
        except OSError:
            return False
        if any(name.endswith(".onnx") for name in names):
            return True
        if any(name.endswith(".pt") for name in names):
            return True
    return False


def _resolve_birder_eu_paths(
    app_config: Mapping[str, Any],
    processor_root: str,
    requested_backend: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.classifier_model_layout import (
        birder_variant_name,
        classifier_torch_rel_pt,
        resolve_birder_bundle_dir,
        resolve_birder_pt_path,
    )
    from inference.selector import resolve_classifier_inference_backend

    resolve_classifier_inference_backend(app_config)
    variant = birder_variant_name(app_config)
    weights_root = Path(processor_root) / "models/classification/weights"

    cfg_pt = str(
        app_config.get("processor.models.classifier")
        or app_config.get("processor.models.classifier_birder_eu")
        or classifier_torch_rel_pt(variant),
    ).strip()
    p_pt = Path(resolve_relative_to_processor_root(cfg_pt, processor_root))

    pt_path = resolve_birder_pt_path(weights_root, variant, p_pt)
    if pt_path.is_file():
        return (str(pt_path), "torch")
    return (str(p_pt), "torch")


def _resolve_explicit_classifier(
    app_config: Mapping[str, Any],
    processor_root: str,
    *,
    engine_label: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.selector import resolve_classifier_inference_backend

    requested = resolve_classifier_inference_backend(app_config)
    rel = app_config.get("processor.models.classifier")
    if not rel:
        raise FileNotFoundError(
            f"processor.models.classifier is required for classifier_engine={engine_label!r}",
        )
    p = resolve_relative_to_processor_root(str(rel).strip(), processor_root)
    return (p, "torch")


def resolve_ornimetrics_species_pack(app_config: Mapping[str, Any]) -> str:
    """Return ``nabirds`` for North America, otherwise iNat/CC fallback."""
    override = str(
        app_config.get("processor.ornimetrics_species_pack") or "auto",
    ).strip().lower()
    if override in ("nabirds", "na", "north_america", "north-america"):
        return "nabirds"
    if override in ("inat", "cc", "creative_commons", "creative-commons"):
        return "inat"
    country = str(app_config.get("ebird.country") or "").strip().upper()
    return "nabirds" if country in {"US", "CA"} else "inat"


def _resolve_chriamue_classifier(
    app_config: Mapping[str, Any],
    processor_root: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.efficientnet_b2_classifier import EfficientNetB2Classifier
    from inference.selector import (
        onnxruntime_classifier_available,
        resolve_classifier_inference_backend,
    )

    requested = resolve_classifier_inference_backend(app_config)
    rel = (
        app_config.get("processor.models.classifier_chriamue")
        or app_config.get("processor.models.classifier")
        or app_config.get("processor.models.classifier_efficientnet_b2")
        or "models/classification/chriamue_bird_species_classifier"
    )
    weights_dir = resolve_relative_to_processor_root(str(rel).strip(), processor_root)
    if requested in ("onnxruntime", "auto"):
        try:
            EfficientNetB2Classifier._resolve_onnx_path(weights_dir)
            if onnxruntime_classifier_available():
                return (weights_dir, "onnxruntime")
        except FileNotFoundError:
            pass
    if requested == "onnxruntime":
        raise FileNotFoundError(
            f"ONNX chriamue classifier missing under {weights_dir}",
        )
    return (weights_dir, "torch")


def _resolve_ornimetrics_classifier(
    app_config: Mapping[str, Any],
    processor_root: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.selector import (
        onnxruntime_classifier_available,
        resolve_classifier_inference_backend,
    )

    requested = resolve_classifier_inference_backend(app_config)
    pack = resolve_ornimetrics_species_pack(app_config)
    specific_key = f"processor.models.classifier_ornimetrics_{pack}"
    rel = (
        app_config.get("processor.models.classifier")
        or app_config.get(specific_key)
        or f"models/classification/ornimetrics/species_classifier_{pack}.onnx"
    )
    p = resolve_relative_to_processor_root(str(rel).strip(), processor_root)
    if (
        requested in ("auto", "onnxruntime")
        and p.endswith(".onnx")
        and onnxruntime_classifier_available()
    ):
        return (p, "onnxruntime")
    if p.endswith(".onnx"):
        return (p, "onnxruntime")
    return (p, "torch")


def resolve_classifier_weight_path(
    app_config: Mapping[str, Any],
    processor_root: str,
) -> tuple[str, str]:
    """Return ``(absolute_path, backend)`` for the active classifier."""
    from inference.selector import resolve_classifier_inference_backend

    requested_backend = resolve_classifier_inference_backend(app_config)
    eng = classifier_engine(app_config)
    if eng == "birder_eu":
        return _resolve_birder_eu_paths(app_config, processor_root, requested_backend)
    if eng == "efficientnet_b2":
        explicit = (
            app_config.get("processor.models.classifier")
            or app_config.get("processor.models.classifier_chriamue")
            or app_config.get("processor.models.classifier_efficientnet_b2")
        )
        cfg_engine = str(app_config.get("processor.classifier_engine") or "").strip().lower()
        if cfg_engine in ("chriamue", "bird_species_classifier", "bird-species-classifier"):
            return _resolve_chriamue_classifier(app_config, processor_root)
        if app_config.get("processor.ornimetrics_species_pack") or not explicit:
            return _resolve_ornimetrics_classifier(app_config, processor_root)
        return _resolve_explicit_classifier(
            app_config,
            processor_root,
            engine_label="efficientnet_b2",
        )
    return _resolve_explicit_classifier(app_config, processor_root, engine_label="yolo")
