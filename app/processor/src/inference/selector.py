"""Выбор backend инференса: torch (дефолт), OpenVINO; ONNX Runtime — позже (#371)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any, Mapping

_IMPLEMENTED = frozenset({"torch", "openvino", "auto"})
_PLANNED = frozenset({"onnxruntime", "tensorrt"})
_BACKEND_ALIASES = {"onnx": "onnxruntime"}


def _resolve_backend(
    app_config: Mapping[str, Any] | None,
    *,
    env_key: str,
    config_key: str,
    default: str = "torch",
) -> str:
    """Common backend resolver: env -> config -> default."""
    raw = (os.environ.get(env_key) or "").strip().lower()
    if raw:
        backend = raw
    elif app_config is not None:
        cfg = app_config.get(config_key)
        backend = str(cfg).strip().lower() if cfg is not None else default
    else:
        backend = default
    if not backend:
        backend = default
    return _BACKEND_ALIASES.get(backend, backend)


def resolve_inference_backend(app_config: Mapping[str, Any] | None = None) -> str:
    """
    Приоритет: ``BIRDLENSE_INFERENCE_BACKEND``, затем ``processor.inference_backend``, иначе ``torch``.
    """
    return _resolve_backend(
        app_config,
        env_key="BIRDLENSE_INFERENCE_BACKEND",
        config_key="processor.inference_backend",
    )


def resolve_classifier_inference_backend(
    app_config: Mapping[str, Any] | None = None,
) -> str:
    """
    Отдельный backend для классификатора.

    Приоритет: ``BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND``, затем
    ``processor.classifier_inference_backend``, иначе ``torch``.
    """
    return _resolve_backend(
        app_config,
        env_key="BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND",
        config_key="processor.classifier_inference_backend",
    )


def assert_backend_supported(backend: str) -> None:
    """Проверить, что backend реализован или запланирован с понятной ошибкой."""
    b = _BACKEND_ALIASES.get((backend or "torch").strip().lower(), (backend or "torch").strip().lower())
    if b in _PLANNED:
        raise NotImplementedError(
            f"Inference backend {b!r} is planned (#371) but not implemented yet. Use: {sorted(_IMPLEMENTED)}.",
        )
    if b not in _IMPLEMENTED:
        raise NotImplementedError(
            f"Inference backend {b!r} is not supported. Implemented: {sorted(_IMPLEMENTED)}.",
        )


def openvino_runtime_available() -> bool:
    """Проверить, установлен ли runtime OpenVINO (для auto-fallback)."""
    return importlib.util.find_spec("openvino") is not None
