"""Notification policy helpers for finalized recordings."""

from __future__ import annotations

from typing import Any, Iterable

from processor_config_defaults import MIN_CONFIDENCE_TO_PROCESS, config_float


_INELIGIBLE_DECISION_KINDS = frozenset(
    {
        "review_only_generic",
        "review_only_uncertain_species",
        "frigate_standalone_excluded",
    }
)


def resolve_min_confidence_to_notify(config: Any) -> float:
    raw_notify = config.get("processor.min_confidence_to_notify")
    try:
        if raw_notify is not None and str(raw_notify).strip() != "":
            return float(raw_notify)
        return config_float(config, "processor.min_confidence_to_process", MIN_CONFIDENCE_TO_PROCESS)
    except (TypeError, ValueError):
        return config_float(config, "processor.min_confidence_to_process", MIN_CONFIDENCE_TO_PROCESS)


def notify_suppression_reason(detection: dict, min_notify: float) -> str | None:
    if not bool(detection.get("notification_eligible", True)):
        return "ineligible"
    decision_kind = str(detection.get("decision_kind") or "").strip().lower()
    if decision_kind in _INELIGIBLE_DECISION_KINDS:
        return "ineligible"
    if float(detection.get("confidence") or 0.0) < float(min_notify):
        return "low_confidence"
    return None


def _cfg_bool(config: Any, key: str, default: bool = False) -> bool:
    raw = config.get(key)
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _cfg_rare_list(config: Any) -> set[str]:
    raw = config.get("notifications.smart_alert_rare_species_list")
    if isinstance(raw, str):
        items: Iterable[str] = raw.split(",")
    elif isinstance(raw, (list, tuple, set)):
        items = [str(x) for x in raw]
    else:
        items = []
    return {str(item).strip().lower() for item in items if str(item).strip()}


def smart_alert_suppression_reason(
    config: Any,
    *,
    species: str,
    first_profile_in_clip: bool,
) -> str | None:
    rare_only = _cfg_bool(config, "notifications.smart_alert_rare_species_only", False)
    first_only = _cfg_bool(
        config,
        "notifications.smart_alert_first_profile_sighting",
        False,
    )
    if rare_only:
        rare = _cfg_rare_list(config)
        if rare and str(species or "").strip().lower() not in rare:
            return "smart_alert_not_rare"
    if first_only and not bool(first_profile_in_clip):
        return "smart_alert_not_first_profile"
    return None
