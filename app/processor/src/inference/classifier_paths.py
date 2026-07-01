"""Resolve classifier weight path — birder_eu (Orin prod) or YOLO-cls fallback."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


def classifier_engine(app_config: Mapping[str, Any]) -> str:
    raw = app_config.get("processor.classifier_engine")
    eng = str(raw).strip().lower() if raw is not None else "birder_eu"
    if eng in ("birder", "birder_eu", "birder-eu", "eu-common", "eu_common"):
        return "birder_eu"
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
        return any(name.endswith((".onnx", ".pt")) for name in names)
    return False


def _resolve_birder_eu_paths(
    app_config: Mapping[str, Any],
    processor_root: str,
    requested_backend: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.classifier_model_layout import (
        birder_variant_name,
        classifier_onnx_rel,
        resolve_birder_bundle_dir,
        resolve_birder_model_dir,
        resolve_birder_onnx_path,
        resolve_birder_pt_path,
    )
    from inference.selector import (
        onnxruntime_classifier_available,
        resolve_classifier_inference_backend,
    )

    resolve_classifier_inference_backend(app_config)
    variant = birder_variant_name(app_config)
    cls_root = Path(processor_root) / "models/classification"
    model_dir = resolve_birder_model_dir(cls_root, variant)
    bundle_dir = resolve_birder_bundle_dir(cls_root, variant, model_dir)

    cfg_cls = str(
        app_config.get("processor.models.classifier")
        or app_config.get("processor.models.classifier_birder_eu")
        or classifier_onnx_rel(variant),
    ).strip()
    onnx_path = resolve_birder_onnx_path(bundle_dir, cfg_cls)
    pt_path = resolve_birder_pt_path(bundle_dir, cfg_cls)

    if requested_backend in ("auto", "onnxruntime") and onnxruntime_classifier_available():
        if onnx_path.is_file():
            return (str(onnx_path), "onnxruntime")
    if pt_path.is_file():
        return (str(pt_path), "torch")
    if onnx_path.is_file():
        return (str(onnx_path), "onnxruntime")
    return (str(resolve_relative_to_processor_root(cfg_cls, processor_root)), "onnxruntime")


def _resolve_explicit_classifier(
    app_config: Mapping[str, Any],
    processor_root: str,
    *,
    engine_label: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root

    rel = str(app_config.get("processor.models.classifier") or "").strip()
    if not rel:
        raise FileNotFoundError(f"No processor.models.classifier for engine {engine_label!r}")
    path = resolve_relative_to_processor_root(rel, processor_root)
    backend = "onnxruntime" if path.endswith(".onnx") else "torch"
    return (path, backend)


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
    return _resolve_explicit_classifier(app_config, processor_root, engine_label="yolo")
