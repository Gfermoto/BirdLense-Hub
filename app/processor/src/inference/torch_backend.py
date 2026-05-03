"""Загрузка YOLO через Ultralytics: torch (``.pt``) или OpenVINO IR (export ``format=openvino``, #371)."""

from __future__ import annotations

import os
from typing import Any


def _ensure_openvino_pkg() -> None:
    try:
        import openvino  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "OpenVINO inference requires the openvino package. "
            "Example: pip install openvino (then export weights with yolo export format=openvino).",
        ) from e


def _apply_openvino_runtime_tuning(*, profile: str, num_requests: int, model_cache_enabled: bool) -> None:
    """
    Export OpenVINO runtime hints via env vars before model creation.

    This keeps tuning centralized for both live processor and offline scripts.
    """
    prof = (profile or "latency").strip().lower()
    if prof not in {"latency", "throughput"}:
        prof = "latency"
    os.environ["OV_PERFORMANCE_HINT"] = prof.upper()
    if int(num_requests or 0) > 0:
        os.environ["OV_NUM_REQUESTS"] = str(int(num_requests))
    else:
        os.environ.pop("OV_NUM_REQUESTS", None)
    if model_cache_enabled:
        os.environ["OV_ENABLE_MODEL_CACHING"] = "1"
        cache_dir = os.environ.get("OV_CACHE_DIR") or os.path.join("data", "processor", "ov_cache")
        os.environ["OV_CACHE_DIR"] = cache_dir


def load_yolo_detector(
    model_path: str,
    *,
    backend: str = "torch",
    openvino_profile: str = "latency",
    openvino_num_requests: int = 0,
    openvino_model_cache_enabled: bool = True,
) -> Any:
    """
    Загрузить бинарный детектор.

    - ``torch``: ``.pt`` чекпоинт (дефолт).
    - ``openvino``: путь к каталогу экспорта OpenVINO или к ``.xml`` (тот же API ``track()`` в Ultralytics).
    """
    b = (backend or "torch").strip().lower()
    if b == "onnxruntime":
        # Селектор по умолчанию всё ещё блокирует onnx в assert_backend_supported (#371).
        # Когда будем подключать ORT: yolo export format=onnx + onnxruntime.InferenceSession
        # или API Ultralytics для ONNX — расширить ветку здесь.
        raise NotImplementedError(
            "ONNX Runtime for binary detector is not implemented yet (#371). "
            "Use torch or openvino, or export OpenVINO IR (yolo export format=openvino).",
        )
    from ultralytics import YOLO

    if b == "torch":
        return YOLO(model_path, task="detect")
    if b == "openvino":
        _ensure_openvino_pkg()
        _apply_openvino_runtime_tuning(
            profile=openvino_profile,
            num_requests=openvino_num_requests,
            model_cache_enabled=bool(openvino_model_cache_enabled),
        )
        return YOLO(model_path, task="detect")
    raise ValueError(f"Unknown detector backend: {backend!r}")


def load_yolo_classifier(model_path: str) -> Any:
    """Классификатор видов пока только torch ``.pt`` (Phase 2 MVP)."""
    from ultralytics import YOLO

    return YOLO(model_path, task="classify")
