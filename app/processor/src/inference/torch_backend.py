"""YOLO loading through Ultralytics: torch ``.pt`` or OpenVINO IR."""

from __future__ import annotations

from typing import Any


def _ensure_openvino_pkg() -> None:
    try:
        import openvino  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "OpenVINO inference requires the openvino package. "
            "Example: pip install openvino, then export with yolo format=openvino.",
        ) from e


def load_yolo_detector(model_path: str, *, backend: str = "torch") -> Any:
    """
    Загрузить бинарный детектор.

    - ``torch``: ``.pt`` чекпоинт (дефолт).
    - ``openvino``: export dir or ``.xml`` through Ultralytics ``track()``.
    - ``tensorrt``: Jetson target ``.engine``; native adapter is gated.
    """
    b = (backend or "torch").strip().lower()
    if b == "onnxruntime":
        # Future ORT path: yolo export format=onnx + InferenceSession.
        # или API Ultralytics для ONNX — расширить ветку здесь.
        raise NotImplementedError(
            "ONNX Runtime for binary detector is not implemented yet (#371). "
            "Use torch/openvino or export OpenVINO IR.",
        )
    from ultralytics import YOLO

    if b in {"torch", "tensorrt"}:
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
