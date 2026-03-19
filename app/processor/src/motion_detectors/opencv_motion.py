"""
OpenCV-based motion detector. Fallback when MQTT (Frigate) is unavailable.
"""
import logging
import time

import cv2

logger = logging.getLogger(__name__)


class OpenCVMotionDetector:
    """
    Motion detection using frame differencing.
    Blocks in detect() until motion is found, calling capture_fn for frames.
    check_every_n_frames: analyze only every N-th frame (1 = every frame); reduces CPU at high FPS.
    """

    def __init__(self, capture_fn, threshold=25, min_contour_area=500, check_interval=0.1, check_every_n_frames=1):
        self.capture_fn = capture_fn
        self.threshold = threshold
        self.min_contour_area = min_contour_area
        self.check_interval = check_interval
        self.check_every_n_frames = max(1, int(check_every_n_frames or 1))
        self._prev_gray = None
        self._frame_count = 0
        self.logger = logging.getLogger(__name__)

    def _should_analyze(self):
        self._frame_count += 1
        return (self._frame_count % self.check_every_n_frames) == 0

    def detect(self):
        """Block until motion detected. Returns True when motion found."""
        while True:
            frame = self.capture_fn()
            if frame is None:
                time.sleep(self.check_interval)
                continue
            if not self._should_analyze():
                time.sleep(self.check_interval)
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            if self._prev_gray is None:
                self._prev_gray = gray
                time.sleep(self.check_interval)
                continue
            diff = cv2.absdiff(self._prev_gray, gray)
            thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            motion = any(cv2.contourArea(c) >= self.min_contour_area for c in contours)
            self._prev_gray = gray
            if motion:
                self.logger.debug("Motion detected")
                return True
            time.sleep(self.check_interval)

    def check(self):
        """One iteration: returns True if motion detected (for OR with Frigate)."""
        frame = self.capture_fn()
        if frame is None:
            return False
        if not self._should_analyze():
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self._prev_gray is None:
            self._prev_gray = gray
            return False
        diff = cv2.absdiff(self._prev_gray, gray)
        thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        motion = any(cv2.contourArea(c) >= self.min_contour_area for c in contours)
        self._prev_gray = gray
        if motion:
            self.logger.debug("Motion detected")
            return True
        return False
