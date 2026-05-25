"""OpenCV motion on each camera stream with per-camera masks."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class OpenCVMultiCameraMotionDetector:
    """OR several OpenCV detectors; exposes which camera fired."""

    def __init__(self, detectors: list[tuple[str, Any]]) -> None:
        self._detectors = [(cid, det) for cid, det in detectors if det is not None]
        self._triggered_camera: str | None = None

    def detect(self) -> bool:
        poll_interval = 0.05
        while True:
            for camera_id, detector in self._detectors:
                if detector.check():
                    self._triggered_camera = camera_id
                    logger.info("Motion: opencv trigger camera=%s", camera_id)
                    return True
            time.sleep(poll_interval)

    def check(self) -> bool:
        for camera_id, detector in self._detectors:
            if detector.check():
                self._triggered_camera = camera_id
                return True
        return False

    def get_triggered_camera(self) -> str | None:
        return self._triggered_camera

    def get_triggered_by(self) -> str:
        return "opencv"

    def get_opencv_diagnostics(self) -> dict | None:
        if not self._triggered_camera:
            return None
        for camera_id, detector in self._detectors:
            if camera_id != self._triggered_camera:
                continue
            fn = getattr(detector, "get_opencv_diagnostics", None) or getattr(
                detector, "diagnostics", None
            )
            if callable(fn):
                data = fn()
                if isinstance(data, dict):
                    data = dict(data)
                    data["camera_id"] = camera_id
                    return data
        return None

    def diagnostics(self) -> dict:
        diag = self.get_opencv_diagnostics()
        if isinstance(diag, dict):
            return diag
        return {"camera_id": self._triggered_camera, "detectors": len(self._detectors)}
