"""Ранняя настройка OpenCV до первого VideoCapture (меньше шума h264/rtsp).

Вызывать из main.py до импорта processor_bootstrap (он тянет go2rtc → cv2).
"""

from __future__ import annotations

import logging
import os

_done = False
_logger = logging.getLogger(__name__)


def configure_opencv_ffmpeg_logging() -> None:
    """Идемпотентно: env + уровень логов OpenCV."""
    global _done
    if _done:
        return
    _done = True
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    # FFmpeg backend внутри OpenCV — тише декодер в docker logs
    os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "quiet")
    try:
        import cv2

        utils = getattr(cv2, "utils", None)
        log_mod = getattr(utils, "logging", None) if utils else None
        if log_mod is not None and hasattr(log_mod, "setLogLevel"):
            level = getattr(log_mod, "LOG_LEVEL_ERROR", None)
            if level is None:
                level = getattr(log_mod, "LOG_LEVEL_SILENT", 0)
            log_mod.setLogLevel(level)
    except Exception:
        _logger.debug("OpenCV/ffmpeg log level init failed", exc_info=True)
