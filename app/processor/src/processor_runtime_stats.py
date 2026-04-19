"""In-memory runtime counters/gauges/latencies with JSON diagnostics."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
import tempfile


_lock = threading.Lock()
logger = logging.getLogger(__name__)
_counters: dict[str, int] = defaultdict(int)
_gauges: dict[str, float | int | str | bool | None] = {}
_latency_samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=200))
_last_flush_at = 0.0


def _data_dir() -> str:
    return (os.environ.get("DATA_DIR") or "data").strip() or "data"


def snapshot_path() -> Path:
    """Return processor runtime snapshot path and ensure parent exists."""
    path = Path(_data_dir()) / "diagnostics" / "processor_runtime_stats.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def inc_counter(name: str, delta: int = 1) -> None:
    """Increment a named counter and flush snapshot opportunistically."""
    with _lock:
        _counters[str(name)] += int(delta)
    _safe_flush_runtime_stats_snapshot()


def set_gauge(name: str, value) -> None:
    """Set a named gauge and flush snapshot opportunistically."""
    with _lock:
        _gauges[str(name)] = value
    _safe_flush_runtime_stats_snapshot()


def observe_timing(name: str, value_ms: float) -> None:
    """Record one latency sample in milliseconds."""
    try:
        val = float(value_ms)
    except (TypeError, ValueError):
        return
    if val < 0:
        return
    with _lock:
        _latency_samples[str(name)].append(val)
    _safe_flush_runtime_stats_snapshot()


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = max(0, min(len(vals) - 1, int(round((len(vals) - 1) * q))))
    return round(float(vals[idx]), 3)


def runtime_stats_snapshot() -> dict:
    """Build a serializable snapshot of counters, gauges and latency quantiles."""
    with _lock:
        latency_ms = {}
        for name, samples in _latency_samples.items():
            vals = list(samples)
            if not vals:
                continue
            latency_ms[f"{name}_count"] = len(vals)
            latency_ms[f"{name}_last"] = round(vals[-1], 3)
            latency_ms[f"{name}_p50"] = _quantile(vals, 0.5)
            latency_ms[f"{name}_p95"] = _quantile(vals, 0.95)
            latency_ms[f"{name}_max"] = round(max(vals), 3)
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "counters": dict(sorted(_counters.items())),
            "gauges": dict(sorted(_gauges.items())),
            "latency_ms": latency_ms,
        }


def flush_runtime_stats_snapshot(*, force: bool = False) -> Path:
    """Write snapshot JSON to disk, throttled unless force=True."""
    global _last_flush_at
    now = time.time()
    if not force and now - _last_flush_at < 1.0:
        return snapshot_path()
    body = runtime_stats_snapshot()
    path = snapshot_path()
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
    ) as tmp:
        tmp.write(json.dumps(body, ensure_ascii=False, indent=2))
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)
    _last_flush_at = now
    return path


def _safe_flush_runtime_stats_snapshot() -> Path | None:
    """Best-effort flush: diagnostics must never break hot paths."""
    try:
        return flush_runtime_stats_snapshot()
    except OSError as exc:
        logger.warning("Runtime stats snapshot flush failed: %s", exc)
        return None


def reset_runtime_stats_for_tests() -> None:
    """Reset all in-memory state used by unit tests."""
    global _last_flush_at
    with _lock:
        _counters.clear()
        _gauges.clear()
        _latency_samples.clear()
    _last_flush_at = 0.0
