"""Build /api/debug/motion-preview — MOG2 / static calibration overlay (SOTA-08)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests

from app_config.app_config import app_config
from app_config.cameras import get_valid_cameras
from services.status_service import _go2rtc_auth, resolve_go2rtc_base_url

logger = logging.getLogger(__name__)

_PROCESSOR_SRC = Path(__file__).resolve().parents[2] / "processor" / "src"
if str(_PROCESSOR_SRC) not in sys.path:
    sys.path.insert(0, str(_PROCESSOR_SRC))

from motion_calibration_preview import (  # noqa: E402
    build_detection_mog2_preview,
    build_trigger_mog2_preview,
    calibration_warnings,
)


def _flatten_processor_cfg() -> dict[str, Any]:
    merged = app_config.config or {}
    proc = dict(merged.get("processor") or {})
    for key, value in merged.items():
        if key.startswith("processor."):
            proc[key.split(".", 1)[1]] = value
    return proc


def _runtime_cfg_dict() -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in (app_config.config or {}).items():
        flat[str(key)] = value
    proc = _flatten_processor_cfg()
    for k, v in proc.items():
        flat[f"processor.{k}"] = v
    return flat


def _fetch_camera_frame_bgr(camera_id: str | None) -> tuple[np.ndarray | None, str | None]:
    video_cfg = app_config.get("video") or {}
    cameras = get_valid_cameras(
        video_config=video_cfg if isinstance(video_cfg, dict) else None,
    )
    if not cameras:
        return None, "no_cameras_configured"
    target = (camera_id or "").strip()
    chosen = None
    for cam in cameras:
        cid = str(cam.get("id") or "").strip()
        if not target or cid == target:
            chosen = cam
            break
    if chosen is None:
        chosen = cameras[0]
    stream_name = str(chosen.get("stream_name") or chosen.get("id") or "").strip()
    detect_name = str(chosen.get("detect_stream_name") or "").strip()
    probe_stream = detect_name or stream_name
    if not probe_stream:
        return None, "camera_missing_stream_name"
    base = resolve_go2rtc_base_url()
    auth = _go2rtc_auth()
    urls = [
        f"{base}/api/frame.jpeg?src={probe_stream}",
    ]
    port = (app_config.get("general.port") or "").strip()
    if not port:
        import os

        port = (os.environ.get("BIRDLENSE_PORT") or "8080").strip()
    urls.append(f"http://127.0.0.1:{port}/go2rtc/api/frame.jpeg?src={probe_stream}")
    for url in urls:
        if not url:
            continue
        try:
            r = requests.get(url, auth=auth, timeout=8)
            if r.status_code != 200 or not r.content:
                continue
            arr = np.frombuffer(r.content, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None and frame.size > 0:
                return frame, None
        except Exception as exc:
            logger.debug("motion preview frame fetch failed %s: %s", url, exc)
    return None, "frame_fetch_failed"


def build_motion_preview_debug_payload(
    *,
    camera_id: str | None = None,
    mode: str = "detection_mog2",
    overrides: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """Return JSON body and HTTP status."""
    mode_norm = (mode or "detection_mog2").strip().lower()
    if mode_norm not in {"detection_mog2", "trigger_mog2", "static"}:
        return {"error": "invalid_mode", "allowed": ["detection_mog2", "trigger_mog2", "static"]}, 400

    frame, err = _fetch_camera_frame_bgr(camera_id)
    if frame is None:
        return {"error": err or "no_frame", "camera_id": camera_id}, 503

    overrides = overrides or {}
    proc = _flatten_processor_cfg()
    proc.update(overrides.get("processor") or {})
    triggers = dict(app_config.get("triggers") or {})
    opencv_cfg = dict(triggers.get("opencv") or {})
    opencv_cfg.update(overrides.get("triggers", {}).get("opencv") or overrides.get("opencv") or {})

    try:
        if mode_norm == "trigger_mog2":
            body = build_trigger_mog2_preview(frame, opencv_cfg)
            body["warnings"] = calibration_warnings(
                mode=mode_norm,
                foreground_pixel_fraction=float(body.get("foreground_pixel_fraction") or 0),
                processor_cfg=proc,
                opencv_cfg=opencv_cfg,
            )
        else:
            runtime = _runtime_cfg_dict()
            for k, v in proc.items():
                runtime[f"processor.{k}"] = v
            from scene_adaptive import SceneAdaptiveConfig  # noqa: E402

            scene_cfg = SceneAdaptiveConfig.from_runtime_cfg(runtime)
            body = build_detection_mog2_preview(frame, scene_cfg)
            body["warnings"] = calibration_warnings(
                mode="detection_mog2",
                foreground_pixel_fraction=float(body.get("foreground_pixel_fraction") or 0),
                processor_cfg=proc,
                opencv_cfg=opencv_cfg,
            )
            if mode_norm == "static":
                body["mode"] = "static"
                body["static_filter"] = {
                    "static_object_suppression_enabled": proc.get("static_object_suppression_enabled"),
                    "static_scene_bird_min_confidence": proc.get("static_scene_bird_min_confidence"),
                    "static_temporal_max_jitter_px": proc.get("static_temporal_max_jitter_px"),
                }
    except Exception as exc:
        logger.exception("motion preview render failed")
        return {"error": "render_failed", "detail": str(exc)}, 500

    body["camera_id"] = camera_id or ""
    body["frame_shape"] = [int(frame.shape[1]), int(frame.shape[0])]
    return body, 200
