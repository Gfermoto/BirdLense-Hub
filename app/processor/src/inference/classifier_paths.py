"""Resolve classifier weight path for torch/OpenVINO/ONNX backends (YOLO-cls or EfficientNetB2)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


def classifier_engine(app_config: Mapping[str, Any]) -> str:
    """``birder_eu`` (707 EU, default) | ``efficientnet_b2`` (global 525) | ``yolo`` (legacy)."""
    raw = app_config.get("processor.classifier_engine")
    eng = str(raw).strip().lower() if raw is not None else "birder_eu"
    if eng in ("birder", "birder_eu", "birder-eu", "eu-common", "eu_common"):
        return "birder_eu"
    if eng in ("efficientnet", "efficientnet_b2", "hf_efficientnet_b2", "birds_efficientnet_b2"):
        return "efficientnet_b2"
    return "yolo"


def _birder_weights_subdir(app_config: Mapping[str, Any]) -> str:
    from inference.birder_eu_classifier import default_birder_variant

    variant = default_birder_variant(app_config)
    return f"birder_{variant.replace('-', '_')}"


def classifier_weights_available(path: str) -> bool:
    """Classifier checkpoint (.pt), OpenVINO IR (dir/.xml), or HF saved model dir."""
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
        if "config.json" in names and (
            "model.safetensors" in names or "pytorch_model.bin" in names
        ):
            return True
    return False


def _resolve_efficientnet_paths(
    app_config: Mapping[str, Any],
    processor_root: str,
    requested_backend: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.selector import (
        onnxruntime_classifier_available,
        openvino_runtime_available,
        resolve_classifier_inference_backend,
    )

    backend = resolve_classifier_inference_backend(app_config)
    default_torch = "models/classification/weights/birds_classifier_efficientnetb2"
    default_bundle = "models/classification/weights/birds_classifier_efficientnetb2_openvino"

    env_onnx = (os.environ.get("BIRDLENSE_CLASSIFIER_ONNX_PATH") or "").strip()
    if env_onnx:
        p_onnx = env_onnx if os.path.isabs(env_onnx) else resolve_relative_to_processor_root(env_onnx, processor_root)
    else:
        cfg_onnx = str(
            app_config.get("processor.models.classifier_efficientnet_b2_onnx")
            or app_config.get("processor.models.classifier_efficientnet_b2_openvino")
            or default_bundle,
        ).strip()
        p_onnx = resolve_relative_to_processor_root(cfg_onnx, processor_root)

    cfg_torch = str(
        app_config.get("processor.models.classifier_efficientnet_b2") or default_torch,
    ).strip()
    p_torch = resolve_relative_to_processor_root(cfg_torch, processor_root)

    bundle = Path(p_onnx) if p_onnx else None
    ov_xml = bundle / "birds_classifier_260.xml" if bundle else None
    ov_ready = bool(
        bundle
        and ov_xml
        and ov_xml.is_file()
        and openvino_runtime_available()
    )
    onnx_ready = bool(
        bundle
        and onnxruntime_classifier_available()
        and (
            (bundle / "birds_classifier_260.onnx").is_file()
            or (bundle / "birds_classifier.onnx").is_file()
            or (bundle.suffix == ".onnx" and bundle.is_file())
        )
    )

    if requested_backend == "openvino":
        if ov_ready:
            return (p_onnx, "openvino")
        raise FileNotFoundError(
            f"EfficientNetB2 OpenVINO IR missing: {ov_xml}. "
            "Run scripts/export_classifier_to_openvino.py",
        )

    if requested_backend == "onnxruntime":
        if onnx_ready:
            return (p_onnx, "onnxruntime")
        raise FileNotFoundError(f"EfficientNetB2 ONNX bundle missing under {p_onnx}")

    if requested_backend == "auto":
        if ov_ready:
            return (p_onnx, "openvino")
        if onnx_ready:
            return (p_onnx, "onnxruntime")
        if classifier_weights_available(p_torch):
            return (p_torch, "torch")

    if ov_ready:
        return (p_onnx, "openvino")
    if classifier_weights_available(p_torch):
        return (p_torch, "torch")
    if onnx_ready:
        return (p_onnx, "onnxruntime")
    return (p_torch, "torch")


def _resolve_birder_eu_paths(
    app_config: Mapping[str, Any],
    processor_root: str,
    requested_backend: str,
) -> tuple[str, str]:
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.selector import openvino_runtime_available, resolve_classifier_inference_backend

    backend = resolve_classifier_inference_backend(app_config)
    subdir = _birder_weights_subdir(app_config)
    default_torch = f"models/classification/weights/{subdir}"
    default_bundle = f"models/classification/weights/{subdir}_openvino"

    cfg_torch = str(app_config.get("processor.models.classifier_birder_eu") or default_torch).strip()
    p_torch = resolve_relative_to_processor_root(cfg_torch, processor_root)

    cfg_ov = str(
        app_config.get("processor.models.classifier_birder_eu_openvino") or default_bundle,
    ).strip()
    p_ov = resolve_relative_to_processor_root(cfg_ov, processor_root)

    bundle = Path(p_ov)
    ov_xml = bundle / "openvino_model.xml"
    ov_ready = bool(bundle.is_dir() and ov_xml.is_file() and openvino_runtime_available())

    if requested_backend == "openvino":
        if ov_ready:
            return (p_ov, "openvino")
        raise FileNotFoundError(
            f"Birder EU OpenVINO IR missing: {ov_xml}. "
            "Run scripts/export_birder_classifier_to_openvino.py",
        )

    if requested_backend == "auto":
        if ov_ready:
            return (p_ov, "openvino")
        if classifier_weights_available(p_torch):
            return (p_torch, "torch")

    if ov_ready:
        return (p_ov, "openvino")
    if classifier_weights_available(p_torch):
        return (p_torch, "torch")
    return (p_torch, "torch")


def resolve_classifier_weight_path(
    app_config: Mapping[str, Any],
    processor_root: str,
) -> tuple[str, str]:
    """
    Return ``(absolute_path, classifier_backend)``.

    - ``birder_eu``: Birder eu-common 707 species (Collins).
    - ``efficientnet_b2``: HF dir or OpenVINO IR export.
    - ``yolo``: legacy Ultralytics classify ``best.pt`` / ``best_openvino_model``.
    """
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.selector import (
        openvino_runtime_available,
        resolve_classifier_inference_backend,
    )

    requested_backend = resolve_classifier_inference_backend(app_config)
    eng = classifier_engine(app_config)
    if eng == "birder_eu":
        return _resolve_birder_eu_paths(app_config, processor_root, requested_backend)
    if eng == "efficientnet_b2":
        return _resolve_efficientnet_paths(app_config, processor_root, requested_backend)

    env_ov = (os.environ.get("BIRDLENSE_CLASSIFIER_OPENVINO_PATH") or "").strip()
    if requested_backend in ("openvino", "auto"):
        if env_ov:
            if os.path.isabs(env_ov):
                p = env_ov
            else:
                p = resolve_relative_to_processor_root(env_ov, processor_root)
        else:
            cfg_ov = app_config.get("processor.models.classifier_openvino")
            cfg_ov_s = str(cfg_ov).strip() if cfg_ov is not None else ""
            if cfg_ov_s:
                p = resolve_relative_to_processor_root(
                    cfg_ov_s,
                    processor_root,
                )
            else:
                p = ""
        if requested_backend == "openvino":
            if p and classifier_weights_available(p):
                return (p, "openvino")
        if p and classifier_weights_available(p) and openvino_runtime_available():
            return (p, "openvino")

    default_cls = "models/classification/weights/best.pt"
    rel = app_config.get("processor.models.classifier", default_cls)
    p = resolve_relative_to_processor_root(str(rel).strip(), processor_root)
    return (p, "torch")
