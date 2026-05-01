"""Разовый замер predict бинарного детектора для кэша / эксплуатации (#371)."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def measure_binary_detector_predict_ms(
    model: Any,
    *,
    imgsz: int = 320,
    device: str | None = None,
) -> float | None:
    """
    Один холодный ``predict`` на нулевом кадре (640×640 RGB).

    Возвращает миллисекунды wall-clock или ``None``, если predict недоступен.
    Не падает при ошибке — только логирует debug.
    """
    try:
        import numpy as np
    except ImportError:
        logger.debug("auto_benchmark: numpy missing")
        return None
    try:
        img = np.zeros((640, 640, 3), dtype=np.uint8)
    except Exception:
        return None
    t0 = time.perf_counter()
    try:
        pred_kw: dict[str, Any] = {"verbose": False, "imgsz": int(imgsz)}
        if device:
            pred_kw["device"] = device
        model.predict(img, **pred_kw)
    except Exception as e:
        logger.debug("auto_benchmark predict failed: %s", e)
        return None
    return (time.perf_counter() - t0) * 1000.0
