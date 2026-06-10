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
    if isinstance(far, dict):
        try:
            far_bird = float(far.get("min_confidence_binary_bird"))
        except (TypeError, ValueError):
            far_bird = None
        if far_bird is None or far_bird > 0.08:
            far["min_confidence_binary_bird"] = 0.08
            changed = True

    return changed


def migrate_linear_pipeline(user_config: dict[str, Any]) -> bool:
    """Enable linear stage order (classify before reid/behavior) on upgraded installs."""
    if not isinstance(user_config, dict):
        return False
    proc = user_config.setdefault("processor", {})
    if not isinstance(proc, dict):
        return False
    if str(proc.get("pipeline_mode") or "").strip():
        return False
    proc["pipeline_mode"] = "linear"
    return True


def _migrate_detect_stream_field(value: str) -> tuple[str, bool]:
    """Dahua/Hik-style RTSP: detect substream should use subtype=1 (lores), not subtype=0 (main)."""
    raw = str(value or "").strip()
    if not raw:
        return raw, False
    if "realmonitor" in raw and "subtype=0" in raw:
        return raw.replace("subtype=0", "subtype=1"), True
    return raw, False


def migrate_detect_stream_lores_substream(user_config: dict[str, Any]) -> bool:
    """Fix detect_stream_name accidentally pointing at main RTSP substream (subtype=0)."""
    if not isinstance(user_config, dict):
        return False
    video = user_config.get("video")
    if not isinstance(video, dict):
        return False
    changed = False

    def _walk_cameras(rows: list | None) -> None:
        nonlocal changed
        if not isinstance(rows, list):
            return
        for cam in rows:
            if not isinstance(cam, dict):
                continue
            dsn = cam.get("detect_stream_name")
            if not isinstance(dsn, str):
                continue
            new_dsn, fixed = _migrate_detect_stream_field(dsn)
            if fixed:
                cam["detect_stream_name"] = new_dsn
                changed = True

    _walk_cameras(video.get("cameras"))
    profiles = video.get("camera_profiles")
    if isinstance(profiles, dict):
        for prof in profiles.values():
            if isinstance(prof, dict) and isinstance(prof.get("detect_stream_name"), str):
                new_dsn, fixed = _migrate_detect_stream_field(prof["detect_stream_name"])
                if fixed:
                    prof["detect_stream_name"] = new_dsn
                    changed = True
    return changed


def migrate_remove_pipeline_persist_legacy_aliases(user_config: dict[str, Any]) -> bool:
    """Rewrite deprecated pipeline_mode/persist_mode values (#621); runtime aliases removed."""
    if not isinstance(user_config, dict):
        return False
    changed = False
    proc = user_config.get("processor")
    if isinstance(proc, dict):
        mode = str(proc.get("pipeline_mode") or "").strip().lower()
        if mode == "legacy":
            proc["pipeline_mode"] = "linear"
            changed = True
    det = user_config.get("detection")
    if isinstance(det, dict):
        persist = str(det.get("persist_mode") or "").strip().lower()
        if persist == "legacy":
            det["persist_mode"] = "binary_track_first"
            changed = True
    return changed
