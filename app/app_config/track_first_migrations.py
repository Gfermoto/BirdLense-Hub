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
