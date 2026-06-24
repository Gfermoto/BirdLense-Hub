"""YOLO loading through Ultralytics: torch ``.pt`` or OpenVINO IR."""

from __future__ import annotations

import os
from typing import Any


def _is_jetson_py311() -> bool:
    """Jetson Nano, py3.11 (not the TRT/Torch py3.6 worker)."""
    import sys

    return (
        os.environ.get("BIRDLENSE_PLATFORM", "") == "jetson_nano"
        and sys.version_info[:2] == (3, 11)
    )


def _ensure_openvino_pkg() -> None:
    try:
        import openvino  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "OpenVINO inference requires the openvino package. "
            "Example: pip install openvino, then export with yolo format=openvino.",
        ) from e


def _load_via_trt_client(model_path: str) -> Any:
    """Load detector via Unix socket client (py3.11 → py3.6 CUDA worker)."""
    from inference.tensorrt_yolo_client import load_tensorrt_yolo_client

    return load_tensorrt_yolo_client(model_path)


def load_yolo_detector(model_path: str, *, backend: str = "torch") -> Any:
    """
    Загрузить бинарный детектор.

    - ``torch``: ``.pt`` чекпоинт (дефолт) — на Jetson Nano py3.11 уходит
      в Unix-сокетный воркер (py3.6 CUDA torch / TorchScript).
    - ``openvino``: export dir or ``.xml`` through Ultralytics ``track()``.
    - ``tensorrt``: Jetson target ``.engine``; native adapter is gated.
    """
    b = (backend or "torch").strip().lower()
    if b == "onnxruntime":
        path = str(model_path or "")
        if path.endswith(".onnx"):
            from ultralytics import YOLO

            return YOLO(path, task="detect")
        raise ValueError(f"ONNX Runtime detector requires .onnx path, got {model_path!r}")
    if b == "tensorrt":
        path = str(model_path or "")
        if not path.endswith(".engine"):
            from ultralytics import YOLO

            return YOLO(model_path, task="detect")
        import sys

        if sys.version_info[:2] == (3, 6):
            from inference.tensorrt_yolo_detector import load_tensorrt_yolo_detector

            return load_tensorrt_yolo_detector(path)
        from inference.tensorrt_yolo_client import load_tensorrt_yolo_client

        return load_tensorrt_yolo_client(path)
    if b == "torch":
        # Jetson Nano py3.11: route through Unix socket to py3.6 CUDA worker
        if _is_jetson_py311():
            return _load_via_trt_client(model_path)
        from ultralytics import YOLO

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
