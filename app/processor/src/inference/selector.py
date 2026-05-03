"""Выбор backend инференса: torch (дефолт), OpenVINO; ONNX Runtime — позже (#371)."""

from __future__ import annotations

import os
from typing import Any, Mapping

_IMPLEMENTED = frozenset({"torch", "openvino"})
_PLANNED = frozenset({"onnxruntime", "tensorrt"})
_BACKEND_ALIASES = {"onnx": "onnxruntime"}
_OPENVINO_PROFILES = frozenset({"latency", "throughput"})


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


def resolve_inference_device(app_config: Mapping[str, Any] | None = None) -> str:
    """
    Приоритет: ``BIRDLENSE_INFERENCE_DEVICE``, затем ``processor.inference_device``, иначе ``auto``.

    Полезно для OpenVINO (CPU/GPU/AUTO) и для torch (`cpu`/`cuda`), когда нужно
    сравнить latency профили без изменения кода.
    """
    raw = (os.environ.get("BIRDLENSE_INFERENCE_DEVICE") or "").strip()
    if raw:
        device = raw
    elif app_config is not None:
        cfg = app_config.get("processor.inference_device")
        device = str(cfg).strip() if cfg is not None else "auto"
    else:
        device = "auto"
    if not device:
        return "auto"
    return device


def resolve_openvino_profile(app_config: Mapping[str, Any] | None = None) -> str:
    """OpenVINO performance profile: latency|throughput."""
    env = (os.environ.get("BIRDLENSE_OPENVINO_PROFILE") or "").strip().lower()
    if env:
        raw = env
    elif app_config is not None:
        raw = str(app_config.get("processor.openvino.profile") or "latency").strip().lower()
    else:
        raw = "latency"
    return raw if raw in _OPENVINO_PROFILES else "latency"


def resolve_openvino_num_requests(app_config: Mapping[str, Any] | None = None) -> int:
    """
    Number of OpenVINO async requests.

    - ``0`` means runtime auto.
    - ``>=1`` forces explicit request count.
    """
    env = (os.environ.get("BIRDLENSE_OPENVINO_NUM_REQUESTS") or "").strip()
    raw = env if env else (app_config.get("processor.openvino.num_requests") if app_config is not None else 0)
    try:
        val = int(raw or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, val)


def resolve_openvino_device_policy(device: str) -> list[str]:
    """
    Resolve preferred/fallback device chain for OpenVINO.

    - ``intel:gpu`` or ``gpu`` => [intel:gpu, intel:cpu]
    - ``auto`` => [intel:gpu, intel:cpu]
    - ``intel:cpu`` or ``cpu`` => [intel:cpu]
    - other explicit value => [value]
    """
    d = str(device or "auto").strip().lower()
    if d in {"auto", "intel:gpu", "gpu"}:
        return ["intel:gpu", "intel:cpu"]
    if d in {"intel:cpu", "cpu"}:
        return ["intel:cpu"]
    return [str(device or "auto").strip()]
