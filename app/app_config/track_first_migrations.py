"""Idempotent user_config migrations for track-first / persist_mode rollout."""

from __future__ import annotations

from typing import Any


def migrate_track_first_contract(user_config: dict[str, Any]) -> bool:
    """Align legacy installs with track-first defaults without wiping custom tuning."""
    if not isinstance(user_config, dict):
        return False
    changed = False

    proc = user_config.setdefault("processor", {})
    if not isinstance(proc, dict):
        return changed
    det = user_config.setdefault("detection", {})
    if not isinstance(det, dict):
        return changed

    triggers = proc.get("detect_scheduler_triggers")
    if isinstance(triggers, list):
        normalized = {str(v).strip().lower() for v in triggers if str(v).strip()}
        if "opencv" not in normalized:
            proc["detect_scheduler_triggers"] = ["opencv", *triggers]
            changed = True

    if det.get("strip_review_only_overlay_frames") is True:
        det["strip_review_only_overlay_frames"] = False
        changed = True

    if not str(det.get("persist_mode") or "").strip():
        det["persist_mode"] = "binary_track_first"
        changed = True

    if det.get("track_first_gate_enabled") is None:
        det["track_first_gate_enabled"] = True
        changed = True

    video = user_config.setdefault("video", {})
    cameras = video.get("cameras")
    if isinstance(cameras, list):
        role_by_id = {"BirdBox": "feeder_close", "Forest": "feeder_far"}
        for row in cameras:
            if not isinstance(row, dict):
                continue
            cam_id = str(row.get("id") or "").strip()
            if cam_id and not str(row.get("tuning_role") or "").strip() and cam_id in role_by_id:
                row["tuning_role"] = role_by_id[cam_id]
                changed = True

    return changed


def migrate_classification_first(user_config: dict[str, Any]) -> bool:
    """Simplify live path: classification-first defaults, classifier on all bird sizes."""
    if not isinstance(user_config, dict):
        return False
    changed = False
    det = user_config.setdefault("detection", {})
    proc = user_config.setdefault("processor", {})
    if not isinstance(det, dict) or not isinstance(proc, dict):
        return False

    for key, val in (
        ("weighted_arbiter_enabled", False),
        ("hypothesis_arbitration_enabled", False),
        ("yolo_weak_track_salvage_enabled", False),
    ):
        if det.get(key) is not False:
            det[key] = val
            changed = True

    if not str(det.get("persist_mode") or "").strip():
        det["persist_mode"] = "binary_track_first"
        changed = True

    try:
        skip_frac = float(proc.get("bird_skip_classifier_max_area_frac"))
    except (TypeError, ValueError):
        skip_frac = None
    if skip_frac is not None and skip_frac > 0:
        proc["bird_skip_classifier_max_area_frac"] = 0
        changed = True

    if proc.get("classifier_best_guess_enabled") is None:
        proc["classifier_best_guess_enabled"] = True
        changed = True

    return changed


def migrate_classification_reliability(user_config: dict[str, Any]) -> bool:
    """Birder thresholds, best-guess votes, Forest static reject off via role preset."""
    if not isinstance(user_config, dict):
        return False
    changed = False
    proc = user_config.setdefault("processor", {})
    if not isinstance(proc, dict):
        return False

    try:
        birder_min = float(proc.get("birder_eu_min_confidence"))
    except (TypeError, ValueError):
        birder_min = None
    if birder_min is None or birder_min >= 0.18:
        proc["birder_eu_min_confidence"] = 0.15
        changed = True

    try:
        min_events = int(proc.get("classifier_best_guess_min_events"))
    except (TypeError, ValueError):
        min_events = None
    if min_events is None or min_events > 1:
        proc["classifier_best_guess_min_events"] = 1
        changed = True

    roles = proc.get("camera_tuning_by_role")
    if not isinstance(roles, dict):
        roles = {}
        proc["camera_tuning_by_role"] = roles
    far = roles.setdefault("feeder_far", {})
    if isinstance(far, dict) and far.get("track_static_reject_enabled") is not False:
        far["track_static_reject_enabled"] = False
        changed = True

    return changed
