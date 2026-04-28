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
    from ultralytics import YOLO

    b = (backend or "torch").strip().lower()
    if b == "torch":
        return YOLO(model_path, task="detect")
    if b == "openvino":
        _ensure_openvino_pkg()
        return YOLO(model_path, task="detect")
    raise ValueError(f"Unknown detector backend: {backend!r}")


def load_yolo_classifier(model_path: str) -> Any:
    """Классификатор видов пока только torch ``.pt`` (Phase 2 MVP)."""
    from ultralytics import YOLO

    return YOLO(model_path, task="classify")
