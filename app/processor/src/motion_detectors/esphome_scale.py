"""ESPHome weight polling as a motion-like trigger."""

from __future__ import annotations

import logging
import time

import requests
from requests import exceptions as requests_exceptions

logger = logging.getLogger(__name__)


class ESPHomeScaleMotionDetector:
    """Trigger when absolute weight delta crosses threshold."""

    def __init__(
        self,
        *,
        url: str,
        sensor_id: str,
        min_delta: float,
        debounce_seconds: float = 1.5,
        poll_interval: float = 0.5,
    ) -> None:
        self.base_url = url.rstrip("/")
        self.sensor_id = sensor_id
        self.min_delta = max(0.001, float(min_delta))
        self.debounce_seconds = max(0.2, float(debounce_seconds))
        self.poll_interval = max(0.2, float(poll_interval))
        self._last_value: float | None = None
        self._last_trigger_at = 0.0
        self._http = requests.Session()

    def _fetch_value(self) -> float | None:
        try:
            response = self._http.get(
                f"{self.base_url}/sensor/{self.sensor_id}",
                timeout=3,
            )
            if response.status_code != 200:
                return None
            payload = response.json() or {}
            return float(payload.get("state"))
        except (TypeError, ValueError):
            return None
        except requests_exceptions.JSONDecodeError:
            return None
        except requests_exceptions.RequestException as exc:
            logger.debug("ESPHome scale poll failed: %s", exc)
            return None

    def check_pending(self) -> bool:
        value = self._fetch_value()
        if value is None:
            return False
        if self._last_value is None:
            self._last_value = value
            return False
        delta = abs(value - self._last_value)
        self._last_value = value
        now = time.time()
        if (
            delta < self.min_delta
            or (now - self._last_trigger_at) < self.debounce_seconds
        ):
            return False
        self._last_trigger_at = now
        logger.info(
            "Motion: ESPHome scales delta trigger (|Δ|=%s)",
            round(delta, 4),
        )
        return True

    def detect(self) -> bool:
        while True:
            if self.check_pending():
                return True
            time.sleep(self.poll_interval)
