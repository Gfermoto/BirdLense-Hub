"""Runtime diagnostics snapshots for self-healing root-cause analysis."""

from __future__ import annotations

import faulthandler
import json
import os
import resource
import threading
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from processor_runtime_stats import runtime_stats_snapshot
from processor_support import get_data_dir


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fd_count() -> int:
    try:
        return len(os.listdir("/proc/self/fd"))
    except Exception:
        return -1


def _rss_mb() -> float:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    kb = float(parts[1])
                    return round(kb / 1024.0, 3)
    except Exception:
        pass
    return -1.0


def _queue_depths(mqtt_aggregator: Any | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if mqtt_aggregator is None:
        return out
    q = getattr(mqtt_aggregator, "_publish_queue", None)
    if q is not None and hasattr(q, "qsize"):
        try:
            out["mqtt_publish_queue_depth"] = int(q.qsize())
        except Exception:
            pass
    events = getattr(mqtt_aggregator, "_events", None)
    if isinstance(events, list):
        out["mqtt_events_queue_depth"] = len(events)
    return out


def collect_root_cause_snapshot(*, mqtt_aggregator: Any | None = None) -> dict[str, Any]:
    if not tracemalloc.is_tracing():
        tracemalloc.start(25)
    top = []
    try:
        snap = tracemalloc.take_snapshot()
        for stat in snap.statistics("lineno")[:10]:
            top.append(str(stat))
    except Exception:
        top = []
    return {
        "collected_at": _utc_now_iso(),
        "pid": int(os.getpid()),
        "thread_count": int(threading.active_count()),
        "fd_count": _fd_count(),
        "rss_mb": _rss_mb(),
        "ru_maxrss_kb": int(getattr(resource.getrusage(resource.RUSAGE_SELF), "ru_maxrss", 0)),
        "runtime_stats": runtime_stats_snapshot(),
        "queue_depths": _queue_depths(mqtt_aggregator),
        "tracemalloc_top": top,
    }


def write_root_cause_dump(snapshot: dict[str, Any], *, reason: str) -> dict[str, str]:
    ts = int(time.time())
    base = Path(get_data_dir()) / "diagnostics" / "self_heal"
    base.mkdir(parents=True, exist_ok=True)
    stem = f"{ts}_{str(reason or 'unknown').strip().replace(' ', '_')}"
    json_path = base / f"{stem}.json"
    stack_path = base / f"{stem}.stacks.txt"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=2)
    with open(stack_path, "w", encoding="utf-8") as fh:
        faulthandler.dump_traceback(file=fh, all_threads=True)
    return {
        "diagnostics_json": str(json_path),
        "stack_dump": str(stack_path),
    }
