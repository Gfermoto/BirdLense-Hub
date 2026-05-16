"""Загрузка YOLO через Ultralytics: torch (``.pt``) или OpenVINO IR (export ``format=openvino``, #371)."""

from __future__ import annotations

from typing import Any


def _ensure_openvino_pkg() -> None:
    try:
        import openvino  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "OpenVINO inference requires the openvino package. "
            "Example: pip install openvino (then export weights with yolo export format=openvino).",
        ) from e


def load_yolo_detector(model_path: str, *, backend: str = "torch") -> Any:
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
        return YOLO(model_path, task="detect")
    raise ValueError(f"Unknown detector backend: {backend!r}")


def load_yolo_classifier(model_path: str, *, backend: str = "torch") -> Any:
    """Load species classifier from torch checkpoint or OpenVINO IR."""
    from ultralytics import YOLO

    b = (backend or "torch").strip().lower()
    if b == "torch":
        return YOLO(model_path, task="classify")
    if b == "openvino":
        _ensure_openvino_pkg()
        return YOLO(model_path, task="classify")
    raise ValueError(f"Unknown classifier backend: {backend!r}")
