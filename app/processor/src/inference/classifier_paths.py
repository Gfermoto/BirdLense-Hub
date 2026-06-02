"""Resolve classifier weight path (Birder EU prod — flat ``{variant}.pt`` + ``*_openvino_model``)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


def classifier_engine(app_config: Mapping[str, Any]) -> str:
    """``birder_eu`` (default) | ``efficientnet_b2`` | ``yolo`` — non-birder needs explicit ``models.classifier``."""
    raw = app_config.get("processor.classifier_engine")
    eng = str(raw).strip().lower() if raw is not None else "birder_eu"
    if eng in ("birder", "birder_eu", "birder-eu", "eu-common", "eu_common"):
        return "birder_eu"
    if eng in ("efficientnet", "efficientnet_b2", "hf_efficientnet_b2", "birds_efficientnet_b2"):
        return "efficientnet_b2"
    return "yolo"


def classifier_weights_available(path: str) -> bool:
    if not path:
        return False
    if os.path.isfile(path):
        return path.endswith((".pt", ".xml", ".onnx"))
    if os.path.isdir(path):
        try:
            names = os.listdir(path)
        except OSError:
            return False
        if any(name.endswith(".xml") for name in names):
            return True
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
        classifier_openvino_rel_dir,
        classifier_torch_rel_pt,
        resolve_birder_bundle_dir,
        resolve_birder_pt_path,
    )
    from inference.selector import openvino_runtime_available, resolve_classifier_inference_backend

    resolve_classifier_inference_backend(app_config)
    variant = birder_variant_name(app_config)
    weights_root = Path(processor_root) / "models/classification/weights"

    cfg_pt = str(
        app_config.get("processor.models.classifier")
        or app_config.get("processor.models.classifier_birder_eu")
        or classifier_torch_rel_pt(variant),
    ).strip()
    p_pt = Path(resolve_relative_to_processor_root(cfg_pt, processor_root))

    cfg_ov = str(
        app_config.get("processor.models.classifier_openvino")
        or app_config.get("processor.models.classifier_birder_eu_openvino")
        or classifier_openvino_rel_dir(variant),
    ).strip()
    p_ov = resolve_birder_bundle_dir(
        weights_root, variant, Path(resolve_relative_to_processor_root(cfg_ov, processor_root))
    )

    ov_xml = p_ov / "openvino_model.xml"
    ov_ready = ov_xml.is_file() and openvino_runtime_available()
    pt_ready = resolve_birder_pt_path(weights_root, variant, p_pt).is_file()

    if requested_backend == "openvino":
        if ov_ready:
            return (str(p_ov), "openvino")
        raise FileNotFoundError(
            f"Birder EU OpenVINO IR missing: {ov_xml}. "
            "Run scripts/download_birder_classifier.py && scripts/export_birder_classifier_to_openvino.py",
        )

    pt_path = resolve_birder_pt_path(weights_root, variant, p_pt)

    if requested_backend == "auto":
        if ov_ready:
            return (str(p_ov), "openvino")
        if pt_ready:
            return (str(pt_path), "torch")

    if ov_ready:
        return (str(p_ov), "openvino")
    if pt_ready:
        return (str(pt_path), "torch")
    return (str(p_ov), "torch")


def _resolve_explicit_classifier(
    app_config: Mapping[str, Any],
    processor_root: str,
    *,
    engine_label: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.selector import openvino_runtime_available, resolve_classifier_inference_backend

    requested = resolve_classifier_inference_backend(app_config)
    rel = app_config.get("processor.models.classifier")
    if not rel:
        raise FileNotFoundError(
            f"processor.models.classifier is required for classifier_engine={engine_label!r}",
        )
    p = resolve_relative_to_processor_root(str(rel).strip(), processor_root)
    cfg_ov = app_config.get("processor.models.classifier_openvino")
    if requested in ("openvino", "auto") and cfg_ov:
        p_ov = resolve_relative_to_processor_root(str(cfg_ov).strip(), processor_root)
        if classifier_weights_available(p_ov) and openvino_runtime_available():
            return (p_ov, "openvino")
    if requested == "openvino":
        raise FileNotFoundError(f"OpenVINO classifier path missing for engine={engine_label!r}")
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
        return _resolve_explicit_classifier(app_config, processor_root, engine_label="efficientnet_b2")
    return _resolve_explicit_classifier(app_config, processor_root, engine_label="yolo")
