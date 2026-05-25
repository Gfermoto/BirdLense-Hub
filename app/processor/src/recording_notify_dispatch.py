"""Notification dispatch helpers for finalized recordings."""

from __future__ import annotations

import logging
from typing import Any, Callable

from notify_preview_encode import encode_notify_preview_base64
from recording_notify_errors import notify_error_hint
from recording_notify_policy import (
    notify_suppression_reason,
    resolve_min_confidence_to_notify,
    smart_alert_suppression_reason,
)
from recording_notify_preview_log import write_notify_preview_activity


def notify_unique_species(
    api: Any,
    config: Any,
    *,
    video_detections: list[dict],
    video_output: str,
    video_id: Any,
    encode_func: Callable[[dict, str], tuple[str | None, str]] | None = None,
) -> None:
    """Notify once per species with eligible detections and generated previews."""
    encode = encode_notify_preview_base64 if encode_func is None else encode_func
    seen = set()
    seen_profiles = set()
    for detection in video_detections:
        species = detection.get("species_name") or detection.get("species") or ""
        if not species or species in seen:
            continue
        seen.add(species)
        nickname = str(detection.get("individual_nickname") or "").strip().lower()
        first_profile_in_clip = False
        if nickname:
            if nickname not in seen_profiles:
                first_profile_in_clip = True
            seen_profiles.add(nickname)
        image_base64, preview_source = encode(detection, video_output)
        min_notify = resolve_min_confidence_to_notify(config)
        suppress_reason = notify_suppression_reason(detection, min_notify)
        if suppress_reason is None:
            suppress_reason = smart_alert_suppression_reason(
                config,
                species=species,
                first_profile_in_clip=first_profile_in_clip,
            )
        if suppress_reason == "ineligible":
            logging.info(
                "Notify suppressed for %s (eligible=false, kind=%s, reason=%s)",
                species,
                detection.get("decision_kind"),
                detection.get("decision_reason"),
            )
            continue
        if suppress_reason in {
            "smart_alert_not_rare",
            "smart_alert_not_first_profile",
        }:
            logging.info("Notify suppressed for %s: %s", species, suppress_reason)
            continue
        if image_base64 is None:
            logging.info(
                "Notify %s without photo: no preview (provider=%s, source=%s)",
                species,
                detection.get("detection_provider", "unknown"),
                preview_source,
            )
            continue
        if suppress_reason == "low_confidence":
            logging.info(
                "Notify suppressed for %s: confidence=%.3f < processor.min_confidence_to_notify=%.3f",
                species,
                float(detection.get("confidence") or 0.0),
                min_notify,
            )
            continue
        logging.info(
            "Notify preview source: %s (%s)",
            preview_source,
            species,
        )
        try:
            link = f"videos/{video_id}" if video_id else "live"
            api.notify_species(
                species,
                image_base64=image_base64,
                link=link,
                preview_source=preview_source,
                notification_eligible=True,
            )
            write_notify_preview_activity(
                api,
                species=species,
                video_id=video_id,
                preview_source=preview_source,
                image_base64=image_base64,
            )
        except Exception as exc:
            logging.warning(
                "Notify species failed%s: %s",
                notify_error_hint(exc),
                exc,
            )
