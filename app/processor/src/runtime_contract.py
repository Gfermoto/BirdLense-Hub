"""Shared helpers for the persisted runtime decision contract."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

_FALLBACK_REASONS = {
    "fallback_bird",
    "fallback_rodent",
    "fallback_squirrel",  # устар.: до переименования на Rodent
    "fallback_detector_generic",
    "review_only_generic_bird",
    "frigate_standalone",
    "frigate_standalone_excluded",
}

_ARBITRATION_REASONS = {
    "absorbed_generic_into_species",
    "absorbed_generic_into_frigate_species",
    "species_won_by_multi_source_consensus",
    "downgraded_to_generic_due_to_conflict",
}


def normalize_provider(provider: str | None) -> str:
    raw = str(provider or "").strip().lower()
    if raw == "birdnet_mqtt":
        return "birdnet"
    return raw


def provider_lineage(row: dict) -> list[str]:
    providers = {
        normalize_provider(item) for item in (row.get("contributing_providers") or []) if normalize_provider(item)
    }
    provider = normalize_provider(row.get("detection_provider"))
    if provider and provider != "arbitration":
        providers.add(provider)
    return sorted(providers)


def choose_primary_provider(row: dict) -> str:
    provider = normalize_provider(row.get("detection_provider"))
    if provider and provider != "arbitration":
        return provider
    lineage = provider_lineage(row)
    for candidate in ("yolo", "frigate", "birdnet"):
        if candidate in lineage:
            return candidate
    source = str(row.get("source") or "").strip().lower()
    if (
        source == "video"
        or row.get("classifier_species_name") is not None
        or row.get("detector_label") is not None
        or str(row.get("decision_kind") or "").strip().lower()
        not in {"frigate_standalone", "frigate_standalone_excluded"}
    ):
        return "yolo"
    return provider or "unknown"


def track_id_sort_key(value) -> tuple[int, int]:
    """Sort key for int or spatial-split composite ids (e.g. ``1:s1``)."""
    if value is None:
        return (0, 0)
    text = str(value).strip()
    if ":" in text:
        base, seg = text.split(":", 1)
        try:
            seg_n = int(seg.lstrip("sS") or "0")
        except ValueError:
            seg_n = 0
        try:
            return (int(base), seg_n)
        except ValueError:
            return (0, seg_n)
    try:
        return (int(text), 0)
    except (TypeError, ValueError):
        return (0, 0)


def track_id_is_positive(value) -> bool:
    base, _ = track_id_sort_key(value)
    return base > 0


def yolo_track_present(row: dict) -> bool:
    if "yolo" in provider_lineage(row):
        return True
    provider = choose_primary_provider(row)
    if provider == "yolo":
        return True
    return track_id_is_positive(row.get("track_id"))


def _fallback_reason_from_value(value: str | None) -> str | None:
    reason = str(value or "").strip().lower()
    if not reason:
        return None
    if reason in _FALLBACK_REASONS:
        return reason
    if reason in _ARBITRATION_REASONS:
        return None
    return None


def infer_fallback_reason(row: dict) -> str | None:
    current = _fallback_reason_from_value(row.get("decision_reason"))
    if current:
        return current
    previous = _fallback_reason_from_value(row.get("decision_reason_before_arbitration"))
    if previous:
        return previous
    provider = choose_primary_provider(row)
    if provider == "frigate" and bool(row.get("frigate_standalone")):
        return "frigate_standalone_excluded" if bool(row.get("frigate_merge_suppressed")) else "frigate_standalone"
    return None


def infer_primary_signal(row: dict) -> str:
    kind = str(row.get("decision_kind") or "").strip().lower()
    reason = str(row.get("decision_reason") or "").strip().lower()
    provider = choose_primary_provider(row)
    if kind == "accepted_species":
        return "species_classifier"
    if provider == "frigate" and bool(row.get("frigate_standalone")):
        return "frigate_standalone"
    if kind == "review_only_generic":
        return "generic_visual_guard"
    if kind == "accepted_generic":
        return "detector_generic"
    if kind == "rejected":
        if reason == "rejected_detector_below_store_floor":
            return "detector_rejected"
        if reason == "rejected_classifier_fallback_disabled":
            return "classifier_rejected"
        return "rejected"
    if reason in _ARBITRATION_REASONS:
        return "arbitrated"
    return provider or "unknown"


def infer_threshold_path(row: dict) -> str:
    kind = str(row.get("decision_kind") or "").strip().lower()
    reason = str(row.get("decision_reason") or "").strip().lower()
    previous = str(row.get("decision_reason_before_arbitration") or "").strip().lower()
    classifier_present = row.get("classifier_species_name") is not None
    if kind == "accepted_species":
        return "classifier_threshold"
    if reason == "rejected_classifier_fallback_disabled":
        return "classifier_threshold_blocked_fallback"
    if reason == "rejected_detector_below_store_floor":
        return "detector_store_floor"
    if reason == "review_only_generic_bird":
        return (
            "classifier_threshold_then_generic_guard"
            if classifier_present
            else "detector_store_floor_then_generic_guard"
        )
    if reason in {"fallback_bird", "fallback_rodent", "fallback_squirrel", "fallback_detector_generic"}:
        return "classifier_threshold_then_detector_store_floor" if classifier_present else "detector_store_floor"
    if reason in {"frigate_standalone", "frigate_standalone_excluded"} or bool(row.get("frigate_standalone")):
        return "frigate_standalone_min_score"
    if reason in _ARBITRATION_REASONS:
        if previous:
            if previous in {"frigate_standalone", "frigate_standalone_excluded"}:
                return "frigate_standalone_min_score+arbitration"
            if previous == "review_only_generic_bird":
                return "generic_guard+arbitration"
            if previous in {"fallback_bird", "fallback_rodent", "fallback_squirrel", "fallback_detector_generic"}:
                return "detector_store_floor+arbitration"
        return "arbitration"
    if kind == "rejected":
        return "decision_rejected"
    return "unclassified"


def apply_runtime_contract(row: dict) -> dict:
    primary_provider = choose_primary_provider(row)
    fallback_reason = infer_fallback_reason(row)
    row["primary_provider"] = primary_provider
    row["provider_lineage"] = provider_lineage(row)
    row["yolo_track_present"] = bool(yolo_track_present(row))
    row["primary_signal"] = infer_primary_signal(row)
    row["threshold_path"] = infer_threshold_path(row)
    row["fallback_used"] = bool(fallback_reason)
    row["fallback_reason"] = fallback_reason
    return row


def apply_runtime_contract_rows(rows: Iterable[dict]) -> list[dict]:
    return [apply_runtime_contract(row) for row in list(rows or [])]


def summarize_runtime_contract(
    persisted_tracks: Iterable[dict],
    rejected_tracks: Iterable[dict],
) -> dict:
    persisted = list(persisted_tracks or [])
    rejected = list(rejected_tracks or [])
    persisted_provider_counts = Counter(str(row.get("primary_provider") or "unknown") for row in persisted)
    rejected_provider_counts = Counter(str(row.get("primary_provider") or "unknown") for row in rejected)
    return {
        "persisted_primary_provider_counts": dict(sorted(persisted_provider_counts.items())),
        "rejected_primary_provider_counts": dict(sorted(rejected_provider_counts.items())),
        "persisted_fallback_count": sum(1 for row in persisted if bool(row.get("fallback_used"))),
        "rejected_fallback_count": sum(1 for row in rejected if bool(row.get("fallback_used"))),
        "persisted_yolo_track_count": sum(1 for row in persisted if bool(row.get("yolo_track_present"))),
        "rejected_yolo_track_count": sum(1 for row in rejected if bool(row.get("yolo_track_present"))),
    }
