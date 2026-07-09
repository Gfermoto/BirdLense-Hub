"""Backpressure gauge helpers (#510)."""

from __future__ import annotations

from processor_backpressure import record_classification_queue_drop, record_classification_queue_state
from processor_runtime_stats import reset_runtime_stats_for_tests, runtime_stats_snapshot


def test_record_classification_queue_state_updates_gauges():
    reset_runtime_stats_for_tests()
    record_classification_queue_state(depth=2, maxsize=8, drops_total=1)
    snap = runtime_stats_snapshot()
    assert snap["gauges"]["classification_queue_depth"] == 2
    assert snap["gauges"]["classification_queue_maxsize"] == 8


def test_record_classification_queue_drop_increments_counter():
    reset_runtime_stats_for_tests()
    record_classification_queue_drop(depth=0, maxsize=8, drops_total=1)
    snap = runtime_stats_snapshot()
    assert snap["counters"]["classification_task_drops_total"] >= 1
