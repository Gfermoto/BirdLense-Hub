"""Decision trace activity-log helpers for finalized recordings."""

from __future__ import annotations

import logging
from typing import Any


def write_decision_trace_activity(api: Any, decision_trace: dict[str, Any]) -> None:
    if not api:
        return
    if not (decision_trace.get("persisted_tracks") or decision_trace.get("rejected_tracks")):
        return
    try:
        api.activity_log("decision_trace", decision_trace)
    except Exception:
        logging.exception("Failed to write decision_trace activity log")
