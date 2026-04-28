"""Загрузка моделей через Ultralytics / PyTorch (дефолтный путь)."""

from __future__ import annotations

from typing import Any


def load_yolo_detector(model_path: str) -> Any:
    from ultralytics import YOLO

    return YOLO(model_path, task="detect")


def load_yolo_classifier(model_path: str) -> Any:
    from ultralytics import YOLO

    return YOLO(model_path, task="classify")
