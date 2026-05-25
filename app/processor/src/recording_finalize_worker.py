"""Async finalize worker with bounded queue (W1.1)."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from processor_runtime_stats import inc_counter, observe_timing, set_gauge
from recording_finalize import finalize_motion_recording

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class FinalizeTask:
    """Immutable finalize task envelope."""

    kwargs: dict[str, Any]
    enqueued_at: float = field(default_factory=time.perf_counter)


class FinalizeWorker:
    """Single-consumer finalize queue to decouple hot session loop."""

    def __init__(
        self,
        *,
        maxsize: int = 2,
        enqueue_timeout_s: float = 1.5,
        shutdown_grace_s: float = 120.0,
    ) -> None:
        self._queue: queue.Queue[FinalizeTask] = queue.Queue(
            maxsize=max(1, int(maxsize))
        )
        self._enqueue_timeout_s = max(0.0, float(enqueue_timeout_s))
        self._shutdown_grace_s = max(1.0, float(shutdown_grace_s))
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="recording-finalize-worker",
            daemon=True,
        )

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()
            set_gauge("finalize_worker_alive", 1)
            _log.info(
                "FinalizeWorker started: maxsize=%s enqueue_timeout_s=%.3f",
                self._queue.maxsize,
                self._enqueue_timeout_s,
            )

    def stop(self, *, wait: bool = True) -> None:
        """Request stop; optionally wait for drain."""
        self._stop_event.set()
        if wait and self._thread.is_alive():
            self._thread.join(timeout=self._shutdown_grace_s)
        alive = int(self._thread.is_alive())
        set_gauge("finalize_worker_alive", alive)
        set_gauge("finalize_queue_depth", self._queue.qsize())
        if alive:
            _log.warning("FinalizeWorker stop timeout: thread still alive")
        else:
            _log.info("FinalizeWorker stopped cleanly")

    def enqueue(self, kwargs: dict[str, Any]) -> bool:
        """Queue finalize task; False when queue is saturated."""
        task = FinalizeTask(kwargs=dict(kwargs))
        t0 = time.perf_counter()
        try:
            self._queue.put(task, timeout=self._enqueue_timeout_s)
        except queue.Full:
            inc_counter("recording_finalize_enqueue_full_total")
            set_gauge("finalize_queue_depth", self._queue.qsize())
            return False
        wait_ms = (time.perf_counter() - t0) * 1000.0
        observe_timing("recording_finalize_enqueue_wait", wait_ms)
        inc_counter("recording_finalize_enqueued_total")
        set_gauge("finalize_queue_depth", self._queue.qsize())
        return True

    def queue_depth(self) -> int:
        return int(self._queue.qsize())

    def is_saturated(self) -> bool:
        return self.queue_depth() >= int(self._queue.maxsize)

    def _run(self) -> None:
        while True:
            if self._stop_event.is_set() and self._queue.empty():
                break
            try:
                task = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            lag_ms = (time.perf_counter() - task.enqueued_at) * 1000.0
            observe_timing("recording_finalize_queue_lag", lag_ms)
            t0 = time.perf_counter()
            try:
                finalize_motion_recording(**task.kwargs)
                inc_counter("recording_finalize_worker_success_total")
            except Exception:
                inc_counter("recording_finalize_worker_fail_total")
                _log.exception("FinalizeWorker: finalize task failed")
            finally:
                task_ms = (time.perf_counter() - t0) * 1000.0
                observe_timing("recording_finalize_worker_task", task_ms)
                self._queue.task_done()
                set_gauge("finalize_queue_depth", self._queue.qsize())


def maybe_start_finalize_worker(app_config_obj) -> FinalizeWorker | None:
    """Create/start worker from config; None means synchronous finalize."""
    if not bool(app_config_obj.get("processor.finalize_async_enabled", True)):
        set_gauge("finalize_worker_alive", 0)
        return None
    try:
        maxsize = int(app_config_obj.get("processor.finalize_queue_maxsize") or 2)
    except (TypeError, ValueError):
        maxsize = 2
    try:
        timeout_ms = int(
            app_config_obj.get("processor.finalize_enqueue_timeout_ms") or 1500
        )
    except (TypeError, ValueError):
        timeout_ms = 1500
    try:
        shutdown_grace_s = float(
            app_config_obj.get("processor.finalize_shutdown_grace_seconds")
            or 120.0
        )
    except (TypeError, ValueError):
        shutdown_grace_s = 120.0
    worker = FinalizeWorker(
        maxsize=maxsize,
        enqueue_timeout_s=max(0.0, float(timeout_ms) / 1000.0),
        shutdown_grace_s=shutdown_grace_s,
    )
    worker.start()
    return worker
