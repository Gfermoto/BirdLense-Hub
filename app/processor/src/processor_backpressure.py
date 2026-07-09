"""Backpressure gauges and saturation helpers (#510)."""

from __future__ import annotations

from typing import Any

from processor_runtime_stats import inc_counter, runtime_stats_snapshot, set_gauge


def record_classification_queue_state(*, depth: int, maxsize: int, drops_total: int) -> None:
    set_gauge("classification_queue_depth", int(depth))
    set_gauge("classification_queue_maxsize", int(maxsize))
    set_gauge("classification_task_drops_total", int(drops_total))


def record_classification_queue_drop(*, depth: int, maxsize: int, drops_total: int) -> None:
    inc_counter("classification_task_drops_total")
    record_classification_queue_state(depth=depth, maxsize=maxsize, drops_total=drops_total)


def backpressure_snapshot(*, finalize_worker: Any | None = None) -> dict[str, Any]:
    """Merge runtime stats with live finalize queue depth."""
    snap = runtime_stats_snapshot()
    gauges = dict(snap.get("gauges") or {})
    counters = dict(snap.get("counters") or {})
    if finalize_worker is not None and hasattr(finalize_worker, "queue_depth"):
        try:
            depth = int(finalize_worker.queue_depth())
            gauges["finalize_queue_depth"] = depth
            maxsz = int(getattr(finalize_worker, "_queue", None).maxsize or 0)
            if maxsz:
                gauges["finalize_queue_maxsize"] = maxsz
                gauges["finalize_queue_saturated"] = depth >= maxsz
        except Exception:
            pass
    return {
        "gauges": gauges,
        "counters": counters,
        "latency_ms": snap.get("latency_ms") or {},
        "generated_at": snap.get("generated_at"),
    }
