"""Wall-clock stage timing for ``POST /api/processor/videos`` (#586)."""

from __future__ import annotations

import time
from typing import Any


class IngestTimingRecorder:
    """Lap timer for processor video ingest stages."""

    __slots__ = ("_last", "_start", "stages")

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._last = self._start
        self.stages: dict[str, float] = {}

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.stages[name] = round(max(0.0, (now - self._last) * 1000.0), 3)
        self._last = now

    def finish(self) -> dict[str, float]:
        total_ms = round(max(0.0, (time.perf_counter() - self._start) * 1000.0), 3)
        out: dict[str, float] = dict(self.stages)
        out["total_ms"] = total_ms
        return out


def merge_ingest_timing_response(payload: dict[str, Any], timing: dict[str, float]) -> dict[str, Any]:
    merged = dict(payload)
    merged["ingest_timing_ms"] = timing
    return merged
