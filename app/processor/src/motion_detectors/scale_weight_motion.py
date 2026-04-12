"""Триггер записи по скачку веса на MQTT (доп. вход к Frigate в OrMotionDetector)."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class ScaleWeightMotionPending:
    """Событие «движение» от весов — проверяется в том же цикле, что Frigate/OpenCV."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def fire(self) -> None:
        logger.info("Motion: scales weight delta trigger -> start recording pipeline")
        self._event.set()

    def check_pending(self) -> bool:
        if self._event.is_set():
            self._event.clear()
            return True
        return False
