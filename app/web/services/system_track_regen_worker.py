"""Shim: реализация в ``services.system_track_regen.worker_core`` (#344 фаза C).

Тесты, патчащие глобалы воркера, должны импортировать ``services.system_track_regen.worker_core``.
"""

from __future__ import annotations

from services.system_track_regen.worker_core import (
    manual_conflict_with_detection,
    run_regenerate_tracks_worker,
)

__all__ = ["manual_conflict_with_detection", "run_regenerate_tracks_worker"]
