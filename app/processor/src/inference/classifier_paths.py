"""Resolve classifier weight path for torch/OpenVINO backends."""

from __future__ import annotations

import os
from typing import Any, Mapping


def classifier_weights_available(path: str) -> bool:
    """Classifier checkpoint (.pt) or OpenVINO IR path (dir or .xml)."""
    if os.path.isfile(path):
        return True
    if os.path.isdir(path):
        try:
            return any(name.endswith(".xml") for name in os.listdir(path))
        except OSError:
            return False
    return False


def resolve_classifier_weight_path(
    app_config: Mapping[str, Any],
    processor_root: str,
) -> tuple[str, str]:
    """
    Return ``(absolute_path, classifier_backend)``.

    - torch: resolves ``processor.models.classifier`` (default ``best.pt``).
    - openvino: resolves env ``BIRDLENSE_CLASSIFIER_OPENVINO_PATH`` or
      ``processor.models.classifier_openvino``.
    - auto: prefers openvino if IR exists and runtime is available.
    """
    from inference.binary_paths import resolve_relative_to_processor_root
    from inference.selector import (
        openvino_runtime_available,
        resolve_classifier_inference_backend,
    )

    requested_backend = resolve_classifier_inference_backend(app_config)
    env_ov = (
        os.environ.get("BIRDLENSE_CLASSIFIER_OPENVINO_PATH") or ""
    ).strip()
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
        if (
            p
            and classifier_weights_available(p)
            and openvino_runtime_available()
        ):
            return (p, "openvino")

    default_cls = "models/classification/weights/best.pt"
    rel = app_config.get("processor.models.classifier", default_cls)
    p = resolve_relative_to_processor_root(str(rel).strip(), processor_root)
    return (p, "torch")
