"""OR motion detector: triggers when ANY child detector fires."""

import logging
import time

logger = logging.getLogger(__name__)


class OrMotionDetector:
    """Combines multiple motion detectors with OR logic."""

    def __init__(self, primary=None, additional=None, extras=None, named_detectors=None):
        self._primary = primary
        self._additional = additional
        self._extras = [e for e in (extras or []) if e is not None]
        if named_detectors is not None:
            self._detectors = [(name, det) for name, det in named_detectors if det is not None]
            self._primary = next((det for name, det in self._detectors if name in {"frigate", "primary"}), None)
            self._additional = next((det for name, det in self._detectors if name == "opencv"), None)
            self._extras = [det for name, det in self._detectors if name.startswith("extra_") or name == "scales"]
        else:
            self._detectors = []
            if primary is not None:
                self._detectors.append(("primary", primary))
            if additional is not None:
                self._detectors.append(("additional", additional))
            for i, extra in enumerate(extras or []):
                if extra is not None:
                    self._detectors.append((f"extra_{i}", extra))
        self._triggered_by = None

    def _check_detector(self, detector):
        for fn_name in ("check_pending", "check"):
            fn = getattr(detector, fn_name, None)
            if fn and callable(fn):
                return bool(fn())
        return False

    def _resolve_triggered_detector(self):
        if not self._triggered_by:
            return None
        for name, detector in self._detectors:
            if name == self._triggered_by:
                return detector
        return None

    def detect(self):
        """Block until any detector fires. Returns True."""
        poll_interval = 0.05
        while True:
            if self.check():
                logger.info("Motion: %s trigger", self._triggered_by)
                return True
            time.sleep(poll_interval)

    def check(self) -> bool:
        """Non-blocking poll: True when any child detector fires."""
        for name, detector in self._detectors:
            if self._check_detector(detector):
                self._triggered_by = name
                return True
        return False

    def get_triggered_camera(self):
        """Return triggered camera when current detector exposes it."""
        detector = self._resolve_triggered_detector()
        if detector:
            return getattr(detector, "get_triggered_camera", lambda: None)()
        return None

    def requeue_last_trigger(self):
        """Re-arm the detector that most recently fired when caller delays recording."""
        detector = self._resolve_triggered_detector()
        if detector is None:
            return False
        fn = getattr(detector, "mark_pending", None)
        if callable(fn):
            fn()
            return True
        return False

    def get_triggered_by(self):
        return self._triggered_by

    def has_recent_frigate_activity(self, camera=None, max_age_seconds=0, min_confidence=0.0):
        """Delegate Frigate keepalive checks to primary detector when present."""
        for name, detector in self._detectors:
            if name not in {"frigate", "primary"}:
                continue
            fn = getattr(detector, "has_recent_activity", None)
            if callable(fn):
                return bool(
                    fn(
                        camera=camera,
                        max_age_seconds=max_age_seconds,
                        min_confidence=min_confidence,
                    )
                )
        return False

    def get_last_frigate_event(self):
        for name, detector in self._detectors:
            if name not in {"frigate", "primary"}:
                continue
            fn = getattr(detector, "get_last_frigate_event", None)
            if callable(fn):
                payload = fn()
                if isinstance(payload, dict) and payload:
                    return payload
        return None

    def get_opencv_diagnostics(self):
        for name, detector in self._detectors:
            if name not in {"opencv", "additional"}:
                continue
            fn = getattr(detector, "diagnostics", None)
            if callable(fn):
                payload = fn()
                if isinstance(payload, dict):
                    return payload
        return None

    def stop(self):
        for _, detector in self._detectors:
            if detector and hasattr(detector, "stop"):
                detector.stop()
