"""
OR motion detector: triggers when ANY of the child detectors fires.
Used for Frigate (always when MQTT) + optional additional (OpenCV, MQTT binary, ESPHome).
"""
import logging
import time

logger = logging.getLogger(__name__)


class OrMotionDetector:
    """
    Combines multiple motion detectors with OR logic.
    detect() returns True when the first of any child fires.
    """

    def __init__(self, primary, additional=None):
        """
        primary: main detector (e.g. Frigate) — must have detect() and optionally check_pending()
        additional: optional second detector (OpenCV, MQTT binary, ESPHome)
        """
        self._primary = primary
        self._additional = additional
        self._triggered_by = None

    def _check_primary(self):
        """Non-blocking check for primary (Frigate). Returns True if pending."""
        if not self._primary:
            return False
        check = getattr(self._primary, 'check_pending', None)
        if check:
            return check()
        return False

    def _check_additional(self):
        """One iteration of additional detector. Returns True if motion."""
        if not self._additional:
            return False
        for name in ('check', 'check_pending'):
            fn = getattr(self._additional, name, None)
            if fn and callable(fn):
                return fn()
        return False

    def detect(self):
        """Block until primary OR additional fires. Returns True."""
        poll_interval = 0.05
        while True:
            if self._check_primary():
                self._triggered_by = 'primary'
                logger.info("Motion: primary (Frigate) trigger")
                return True
            if self._check_additional():
                self._triggered_by = 'additional'
                logger.info("Motion: additional trigger")
                return True
            time.sleep(poll_interval)

    def get_triggered_camera(self):
        """For Frigate: return camera. For additional: None."""
        if self._triggered_by == 'primary' and self._primary:
            return getattr(self._primary, 'get_triggered_camera', lambda: None)()
        return None

    def stop(self):
        for d in (self._primary, self._additional):
            if d and hasattr(d, 'stop'):
                d.stop()
