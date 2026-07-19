"""Visit quality contract — named auto-accept vs review-only generic.

Product win is a named species (or Frigate-promoted name), not persist of placeholder Bird.
``db_persist_success`` alone is not a quality signal.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app_config.visit_eligibility import (
    is_generic_bird_species_name,
    is_unidentified_activity_species_name,
)


_PROMOTEABLE_DECISION_REASONS = frozenset(
    {
        "fallback_bird",
        "fallback_rodent",
        "fallback_squirrel",
        "review_only_generic_bird",
        "accepted_binary_track_classifier_deferred",
        "accepted_binary_track_classifier_uncertain",
        "review_only_frigate_trigger_salvage",
    }
)


def is_named_product_species(
    name: str | None,
    *,
    birder_unknown_label: str | None = None,
) -> bool:
    """True when label is a real species for named_share SLOs (not Bird/Unknown/Rodent)."""
    n = str(name or "").strip()
    if not n:
        return False
    return not is_unidentified_activity_species_name(
        n, birder_unknown_label=birder_unknown_label
    )


def is_frigate_promoteable_reason(decision_reason: str | None) -> bool:
    return str(decision_reason or "").strip().lower() in _PROMOTEABLE_DECISION_REASONS


# Taxonomy authority / standalone only — salvage evidence must not exclude Hub rows.
FRIGATE_TAXONOMY_REASONS = frozenset(
    {
        "promoted_by_frigate",
        "frigate_standalone",
        "frigate_standalone_excluded",
        "frigate_trigger_named_accept",
    }
)


def is_frigate_sourced_row(row: Mapping[str, Any] | None) -> bool:
    """True when species/accept came from Frigate taxonomy authority (not Hub).

    ``frigate_trigger_salvage`` / review-salvage reasons are evidence-only and do
    **not** mark a row as Frigate-sourced for ``named_share_hub``.
    """
    if not isinstance(row, Mapping):
        return False
    if bool(row.get("frigate_species_promoted")) or bool(row.get("frigate_standalone")):
        return True
    reason = str(row.get("decision_reason") or "").strip().lower()
    if reason in FRIGATE_TAXONOMY_REASONS:
        return True
    provider = str(row.get("detection_provider") or "").strip().lower()
    if provider != "frigate":
        return False
    # Pure Frigate detection provider: count only when no Hub classifier label.
    if row.get("classifier_species_name") is not None:
        hub_cls = str(row.get("classifier_species_name") or "").strip()
        if hub_cls and is_named_product_species(hub_cls):
            return False
    return True


def apply_frigate_named_accept(row: dict[str, Any], *, species: str, confidence: float | None = None) -> dict[str, Any]:
    """Upgrade a review/generic row to Frigate-authoritative named accept (in-place + return).

    Hub-first: call only when ``frigate_species_authority`` is explicitly enabled.
    """
    promoted = str(species or "").strip()
    if not promoted:
        return row
    row["species_name"] = promoted
    row["species"] = promoted
    row["decision_reason"] = "promoted_by_frigate"
    row["decision_kind"] = "accepted_species"
    row["outcome_bucket"] = "auto_accept"
    row["visit_eligible"] = True
    row["classifier_needs_review"] = False
    row["frigate_species_promoted"] = True
    row["frigate_promoted_label"] = promoted
    if confidence is not None:
        try:
            conf = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            conf = None
        if conf is not None:
            row["confidence"] = max(float(row.get("confidence") or 0.0), conf)
            row["classifier_confidence"] = max(
                float(row.get("classifier_confidence") or 0.0),
                conf,
            )
    # Named Frigate accept may notify when score is usable.
    try:
        notify_floor = float(row.get("confidence") or 0.0)
    except (TypeError, ValueError):
        notify_floor = 0.0
    row["notification_eligible"] = notify_floor >= 0.55
    return row


def _species_of(row: Mapping[str, Any]) -> str:
    return str(row.get("species_name") or row.get("species") or "").strip()


def _frigate_named_labels(
    mqtt_events: Iterable[Mapping[str, Any]] | None,
    *,
    birder_unknown_label: str | None = None,
) -> set[str]:
    out: set[str] = set()
    for ev in mqtt_events or []:
        if str((ev or {}).get("source") or "").strip().lower() != "frigate":
            continue
        raw = ev.get("species") or ev.get("sub_label") or ""
        name = str(raw or "").strip()
        if is_named_product_species(name, birder_unknown_label=birder_unknown_label):
            out.add(name.lower())
        # Prefer sub_label when present even if species is generic bird.
        sub = str(ev.get("sub_label") or "").strip()
        if is_named_product_species(sub, birder_unknown_label=birder_unknown_label):
            out.add(sub.lower())
    return out


def compute_visit_quality(
    *,
    persisted_rows: Iterable[Mapping[str, Any]] | None,
    mqtt_events: Iterable[Mapping[str, Any]] | None = None,
    birder_unknown_label: str | None = None,
) -> dict[str, Any]:
    """Session-level product SLOs.

    ``named_share`` = all persisted named (incl. Frigate-assisted).
    ``named_share_hub`` = Hub YOLO+classifier only (SOTA go metric).
    ``frigate_agreement`` = informative when Frigate is present; not a go gate.
    """
    rows = [r for r in (persisted_rows or []) if isinstance(r, Mapping)]
    total = len(rows)
    named = 0
    hub_rows = 0
    hub_named = 0
    auto_accept = 0
    review_only = 0
    frigate_promoted = 0
    for row in rows:
        sp = _species_of(row)
        frigate_row = is_frigate_sourced_row(row)
        if not frigate_row:
            hub_rows += 1
        if is_named_product_species(sp, birder_unknown_label=birder_unknown_label):
            named += 1
            if not frigate_row:
                hub_named += 1
        kind = str(row.get("decision_kind") or "").strip().lower()
        bucket = str(row.get("outcome_bucket") or "").strip().lower()
        if bucket == "auto_accept" or kind == "accepted_species":
            auto_accept += 1
        if bucket == "review_only" or kind.startswith("review_only"):
            review_only += 1
        if frigate_row:
            frigate_promoted += 1

    frigate_named = _frigate_named_labels(mqtt_events, birder_unknown_label=birder_unknown_label)
    persisted_named = {
        _species_of(r).lower()
        for r in rows
        if is_named_product_species(_species_of(r), birder_unknown_label=birder_unknown_label)
    }
    if frigate_named:
        agreement = round(len(frigate_named & persisted_named) / len(frigate_named), 4)
    else:
        agreement = None

    return {
        "persisted_rows": total,
        "named_rows": named,
        "named_share": (round(named / total, 4) if total else None),
        "hub_persisted_rows": hub_rows,
        "hub_named_rows": hub_named,
        "named_share_hub": (round(hub_named / hub_rows, 4) if hub_rows else None),
        "auto_accept_rows": auto_accept,
        "review_only_rows": review_only,
        "frigate_promoted_rows": frigate_promoted,
        "frigate_named_in_window": len(frigate_named),
        "frigate_agreement": agreement,
        "generic_placeholder_rows": total - named,
    }


def role_detection_flag(
    app_config,
    key: str,
    *,
    camera_id: str | None = None,
    default: bool = False,
    opt_in: bool = True,
) -> bool:
    """Resolve detection.* flag via global + camera_tuning_by_role preset.

    opt_in=True (default): global True OR role True (safe enable helpers).
    opt_in=False: role key wins when present, else global, else default
    (needed to disable gates like require_blind_yolo on frigate_site).
    """
    global_key = key if key.startswith("detection.") else f"detection.{key}"
    short = global_key.split(".", 1)[-1]
    preset: dict[str, Any] = {}
    try:
        from linear_pipeline import _role_preset

        preset = _role_preset(app_config, camera_id)
    except ImportError:
        preset = {}
    if not opt_in:
        if short in preset and preset.get(short) is not None:
            return bool(preset.get(short))
        if app_config.get(global_key) is not None:
            return bool(app_config.get(global_key))
        return bool(default)
    if bool(app_config.get(global_key, False)):
        return True
    if short in preset and preset.get(short) is not None:
        return bool(preset.get(short))
    return bool(default)


def frigate_species_authority(app_config, *, camera_id: str | None = None) -> bool:
    """When true, Frigate named sub_label is an accept authority (not hints-only)."""
    return role_detection_flag(
        app_config,
        "frigate_species_authority",
        camera_id=camera_id,
        default=False,
    )
