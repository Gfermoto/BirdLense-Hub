"""Выбор backend инференса: OpenVINO (дефолт), torch; ONNX Runtime — позже (#371)."""

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
    Приоритет: ``BIRDLENSE_INFERENCE_BACKEND``, затем ``processor.inference_backend``, иначе ``openvino``.
    """
    return _resolve_backend(
        app_config,
        env_key="BIRDLENSE_INFERENCE_BACKEND",
        config_key="processor.inference_backend",
        default="openvino",
    )


def resolve_inference_device(app_config: Mapping[str, Any] | None = None) -> str | None:
    """
    Устройство для вызовов Ultralytics ``track`` / ``predict`` у бинарного детектора.

    Приоритет: ``BIRDLENSE_INFERENCE_DEVICE``, затем ``processor.inference_device``.
    Пустая строка → ``None`` (поведение Ultralytics по умолчанию).

    Примеры для OpenVINO на Intel: ``intel:gpu``, ``intel:cpu``, ``intel:npu``
    (см. документацию Ultralytics OpenVINO).
    """
    raw = (os.environ.get("BIRDLENSE_INFERENCE_DEVICE") or "").strip()
    if not raw and app_config is not None:
        cfg = app_config.get("processor.inference_device")
        raw = str(cfg).strip() if cfg is not None else ""
    return raw or None


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
        default="torch",
    )


def resolve_classifier_inference_device(
    app_config: Mapping[str, Any] | None = None,
) -> str | None:
    """
    Device for species classifier inference.

    Priority: ``BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE``, then
    ``processor.classifier_inference_device``, then detector device
    resolver (``resolve_inference_device``).
    """
    raw = (os.environ.get("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE") or "").strip()
    if not raw and app_config is not None:
        cfg = app_config.get("processor.classifier_inference_device")
        raw = str(cfg).strip() if cfg is not None else ""
    if raw:
        return raw
    return resolve_inference_device(app_config)


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


def resolve_openvino_device_policy(device: str) -> list[str]:
    """
    Развернуть политику устройств OpenVINO для прогрева/ретраев (Ultralytics OpenVINO).

    ``auto`` → сначала iGPU, затем CPU; ``cpu`` и ``intel:cpu`` → только CPU.
    """
    d = (device or "auto").strip().lower()
    if d == "auto":
        return ["intel:gpu", "intel:cpu"]
    if d in ("cpu", "intel:cpu"):
        return ["intel:cpu"]
    return [d]


def resolve_openvino_profile(app_config: Mapping[str, Any] | None = None) -> str:
    """latency / throughput; env ``BIRDLENSE_OPENVINO_PROFILE`` перекрывает конфиг."""
    raw = (os.environ.get("BIRDLENSE_OPENVINO_PROFILE") or "").strip().lower()
    if raw in ("latency", "throughput"):
        return raw
    if app_config is not None:
        cfg = app_config.get("processor.openvino.profile")
        if cfg is not None:
            v = str(cfg).strip().lower()
            if v in ("latency", "throughput"):
                return v
    return "latency"


def resolve_openvino_num_requests(app_config: Mapping[str, Any] | None = None) -> int:
    """Число infer-запросов; env ``BIRDLENSE_OPENVINO_NUM_REQUESTS`` перекрывает конфиг."""
    raw = (os.environ.get("BIRDLENSE_OPENVINO_NUM_REQUESTS") or "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    if app_config is not None:
        cfg = app_config.get("processor.openvino.num_requests")
        if cfg is not None:
            try:
                return max(1, int(cfg))
            except (TypeError, ValueError):
                pass
    return 1
