"""
ESPHome binary sensor motion detector. Polls binary sensor state via HTTP.
"""
import logging
import time

import requests

logger = logging.getLogger(__name__)


class ESPHomeBinaryMotionDetector:
    """Motion detection via ESPHome binary sensor. Polls state, triggers on ON."""

    def __init__(self, url: str, sensor_id: str, poll_interval: float = 0.5):
        self.base_url = url.rstrip("/")
        self.sensor_id = sensor_id
        self.poll_interval = poll_interval
        self._last_trigger = 0.0
        self._cooldown = 2.0  # seconds between triggers

    def _get_state(self) -> bool:
        """Fetch binary sensor state from ESPHome Web API."""
        try:
            r = requests.get(
                f"{self.base_url}/binary_sensor/{self.sensor_id}",
                timeout=3,
            )
            if r.status_code != 200:
                return False
            data = r.json()
            state = data.get("state", "").upper()
            return state in ("ON", "1", "TRUE")
        except Exception as e:
            logger.debug("ESPHome binary sensor poll failed: %s", e)
            return False

    def check(self):
        """One poll: returns True if motion (sensor ON) and cooldown passed (for OR with Frigate)."""
        if self._get_state():
            now = time.time()
            if now - self._last_trigger >= self._cooldown:
                self._last_trigger = now
                logger.info("ESPHome binary sensor: motion ON")
                return True
        return False

    def detect(self):
        """Block until motion (sensor ON). Returns True when detected."""
        while True:
            if self.check():
                return True
            time.sleep(self.poll_interval)
