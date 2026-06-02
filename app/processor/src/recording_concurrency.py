"""Per-camera concurrent recording registry (#589)."""

from __future__ import annotations

import threading
from typing import Any


class RecordingConcurrency:
    """Track active recording sessions and serialize shared YOLO inference."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inference_lock = threading.RLock()
        self._active: set[str] = set()

    @property
    def inference_lock(self) -> threading.RLock:
        return self._inference_lock

    def any_active(self) -> bool:
        with self._lock:
            return bool(self._active)

    def is_active(self, camera_key: str) -> bool:
        with self._lock:
            return camera_key in self._active

    def try_register(self, camera_key: str) -> bool:
        """Mark camera as recording. Returns False if already active."""
        with self._lock:
            if camera_key in self._active:
                return False
            self._active.add(camera_key)
            return True

    def unregister(self, camera_key: str) -> None:
        with self._lock:
            self._active.discard(camera_key)

    def active_peers(self, exclude: str | None = None) -> list[str]:
        with self._lock:
            ex = str(exclude or "").strip()
            return sorted(k for k in self._active if not ex or k != ex)

    def snapshot(self, exclude: str | None = None) -> dict[str, Any]:
        with self._lock:
            active = set(self._active)
        ex = str(exclude or "").strip()
        peers = sorted(k for k in active if not ex or k != ex)
        return {
            "active_count": len(active),
            "peer_cameras": peers,
        }


def concurrent_recording_enabled(app_config, *, camera_count: int) -> bool:
    raw = app_config.get("processor.concurrent_recording_enabled")
    if raw is None:
        return int(camera_count) >= 2
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(raw)
