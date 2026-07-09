"""Resolve which camera id to use when starting a motion recording session."""

from __future__ import annotations

import logging
from typing import Any

from app_config.app_config import app_config

logger = logging.getLogger(__name__)


def resolve_motion_recording_camera_id(
    motion_detector: Any,
    *,
    mqtt_aggregator: Any = None,
    default_camera_id: str | None = None,
) -> str:
    """Return camera id for the next recording.

    Frigate (and scales with camera) expose ``get_triggered_camera``.
    OpenCV does not — on multi-camera sites prefer the camera with the freshest
    Frigate MQTT activity in the hold window instead of blindly using
    ``default_camera_id`` (first entry in ``video.cameras``).
    """
    explicit = getattr(motion_detector, "get_triggered_camera", lambda: None)()
    if explicit:
        return str(explicit)

    triggered_by = str(getattr(motion_detector, "get_triggered_by", lambda: None)() or "").strip().lower()
    if triggered_by == "opencv" and mqtt_aggregator is not None:
        try:
            from app_config.cameras import cameras_for_processor, get_valid_cameras

            proc_cams = cameras_for_processor(
                get_valid_cameras(video_config=(app_config.get("video") or {})),
            )
            camera_ids = [str(c.get("id") or "").strip() for c in proc_cams if str(c.get("id") or "").strip()]
        except Exception:
            camera_ids = []
        if camera_ids:
            try:
                max_age = float(app_config.get("processor.frigate_activity_hold_seconds") or 6.0)
            except (TypeError, ValueError):
                max_age = 6.0
            pick_fn = getattr(mqtt_aggregator, "pick_recent_frigate_camera", None)
            if callable(pick_fn):
                picked = pick_fn(camera_ids=camera_ids, max_age_seconds=max_age)
                if picked:
                    logger.info(
                        "OpenCV trigger: resolved recording camera=%s from recent Frigate MQTT (candidates=%s)",
                        picked,
                        camera_ids,
                    )
                    return str(picked)

    fallback = str(default_camera_id or "").strip() or "_default"
    if triggered_by == "opencv" and fallback != "_default":
        logger.debug(
            "OpenCV trigger: no Frigate camera hint; using default_camera_id=%s",
            fallback,
        )
    return fallback
