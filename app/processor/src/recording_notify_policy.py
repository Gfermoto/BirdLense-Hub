"""Notification policy helpers for finalized recordings."""

from __future__ import annotations

from typing import Any


_INELIGIBLE_DECISION_KINDS = frozenset(
    {
        "review_only_generic",
        "frigate_standalone_excluded",
    }
)


def resolve_min_confidence_to_notify(config: Any) -> float:
    raw_notify = config.get("processor.min_confidence_to_notify")
    try:
        if raw_notify is not None and str(raw_notify).strip() != "":
            return float(raw_notify)
        return float(config.get("processor.min_confidence_to_process") or 0.30)
    except (TypeError, ValueError):
        return float(config.get("processor.min_confidence_to_process") or 0.30)


def notify_suppression_reason(detection: dict, min_notify: float) -> str | None:
    if not bool(detection.get("notification_eligible", True)):
        return "ineligible"
    decision_kind = str(detection.get("decision_kind") or "").strip().lower()
    if decision_kind in _INELIGIBLE_DECISION_KINDS:
        return "ineligible"
    if float(detection.get("confidence") or 0.0) < float(min_notify):
        return "low_confidence"
    return None
