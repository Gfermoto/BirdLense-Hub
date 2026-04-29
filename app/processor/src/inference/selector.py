"""Выбор backend инференса: torch (дефолт), OpenVINO; ONNX Runtime — позже (#371)."""

from __future__ import annotations

import importlib.util
import os
from typing import Any, Mapping

_IMPLEMENTED = frozenset({"torch", "openvino", "auto"})
_PLANNED = frozenset({"onnxruntime", "tensorrt"})
_BACKEND_ALIASES = {"onnx": "onnxruntime"}


def resolve_inference_backend(app_config: Mapping[str, Any] | None = None) -> str:
    """
    Приоритет: ``BIRDLENSE_INFERENCE_BACKEND``, затем ``processor.inference_backend``, иначе ``torch``.
    """
    raw = (os.environ.get("BIRDLENSE_INFERENCE_BACKEND") or "").strip().lower()
    if raw:
        backend = raw
    elif app_config is not None:
        cfg = app_config.get("processor.inference_backend")
        backend = str(cfg).strip().lower() if cfg is not None else "torch"
    else:
        backend = "torch"
    if not backend:
        backend = "torch"
    backend = _BACKEND_ALIASES.get(backend, backend)
    return backend


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
