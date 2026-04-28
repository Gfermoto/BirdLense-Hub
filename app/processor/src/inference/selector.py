"""Выбор backend инференса: torch (дефолт), далее OpenVINO / ORT (#371)."""

from __future__ import annotations

import os
from typing import Any, Mapping

_ALLOWED = frozenset({"torch"})


def resolve_inference_backend(app_config: Mapping[str, Any] | None = None) -> str:
    """
    Приоритет: ``BIRDLENSE_INFERENCE_BACKEND``, затем ``processor.inference_backend``, иначе ``torch``.

    Phase 1: допускается только ``torch``; иные значения — ошибка при сборке стека.
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
    return backend


def assert_backend_supported(backend: str) -> None:
    """Проверить, что backend реализован в этом билде."""
    b = (backend or "torch").strip().lower()
    if b not in _ALLOWED:
        raise NotImplementedError(
            f"Inference backend {b!r} is not implemented in this build (#371). "
            f"Supported: {sorted(_ALLOWED)}. Unset BIRDLENSE_INFERENCE_BACKEND or use torch.",
        )
