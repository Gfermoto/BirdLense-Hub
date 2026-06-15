"""Hi-res BGR crop from main recording MP4 (shared by TG preview, classifier, ReID)."""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_CROP_SOURCES = frozenset({"best_frame_lores", "record_hires", "auto"})


def resolve_enrichment_crop_source(
    app_config: Mapping[str, Any] | None,
    *,
    config_key: str,
    default: str = "auto",
) -> str:
    raw = default
    if app_config is not None:
        raw = str(app_config.get(config_key) or default).strip().lower()
    if raw in _CROP_SOURCES:
        return raw
    return default


def resolve_crop_pad_frac(
    app_config: Mapping[str, Any] | None = None,
    *,
    runtime_cfg: Mapping[str, Any] | None = None,
) -> float:
    raw = 0.06
    for cfg in (runtime_cfg, app_config):
        if cfg is None:
            continue
        try:
            val = cfg.get("processor.enrichment_crop_pad_frac")
            if val is None:
                val = cfg.get("processor.notify_preview_crop_pad_frac")
            if val is not None:
                raw = float(val)
                break
        except (TypeError, ValueError):
            continue
    return max(0.0, min(0.25, raw))


def _shape_hw_from_wh(wh: Any) -> tuple[int, int] | None:
    """Parse config-style [width, height] (e.g. processor.inference_lores_wh)."""
    if not isinstance(wh, (list, tuple)) or len(wh) < 2:
        return None
    try:
        w, h = int(wh[0]), int(wh[1])
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return (h, w)


def _shape_hw_from_metadata(wh: Any) -> tuple[int, int] | None:
    """Parse detection *_shape_hw lists stored as [height, width]."""
    if not isinstance(wh, (list, tuple)) or len(wh) < 2:
        return None
    try:
        h, w = int(wh[0]), int(wh[1])
    except (TypeError, ValueError):
        return None
    if h <= 0 or w <= 0:
        return None
    return (h, w)


def resolve_record_crop_geometry(
    detection: Mapping[str, Any],
    *,
    crop_shape_hw: tuple[int, int],
    runtime_cfg: Mapping[str, Any] | None = None,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """(detector_hw, overlay_hw, playback_hw) for hires bbox remap."""
    playback_hw = crop_shape_hw
    for key in ("playback_shape_hw", "record_shape_hw"):
        raw = detection.get(key)
        shaped = _shape_hw_from_metadata(raw) if isinstance(raw, (list, tuple)) else None
        if shaped is not None:
            playback_hw = shaped
            break

    overlay_hw = playback_hw
    for key in ("overlay_shape_hw", "detect_shape_hw"):
        raw = detection.get(key)
        shaped = _shape_hw_from_metadata(raw) if isinstance(raw, (list, tuple)) else None
        if shaped is not None:
            overlay_hw = shaped
            break
    if overlay_hw == playback_hw and runtime_cfg is not None:
        lores = _shape_hw_from_wh(runtime_cfg.get("processor.inference_lores_wh"))
        if lores is not None:
            overlay_hw = lores

    detector_hw = overlay_hw
    for key in ("detector_shape_hw",):
        raw = detection.get(key)
        shaped = _shape_hw_from_metadata(raw) if isinstance(raw, (list, tuple)) else None
        if shaped is not None:
            detector_hw = shaped
            break

    return detector_hw, overlay_hw, playback_hw


def _bbox_stored_in_playback_space(
    detection: Mapping[str, Any],
    *,
    crop_shape_hw: tuple[int, int],
    runtime_cfg: Mapping[str, Any] | None = None,
) -> bool:
    """Persisted track frames use playback-normalized xyxy when metadata says so."""
    raw_playback = detection.get("playback_shape_hw") or detection.get("record_shape_hw")
    playback_shaped = _shape_hw_from_metadata(raw_playback) if isinstance(raw_playback, (list, tuple)) else None
    if playback_shaped is None or playback_shaped != crop_shape_hw:
        return False
    _, overlay_hw, playback_hw = resolve_record_crop_geometry(
        detection,
        crop_shape_hw=crop_shape_hw,
        runtime_cfg=runtime_cfg,
    )
    return overlay_hw != playback_hw


def remap_bbox_for_record_crop(
    bbox: list[float],
    detection: Mapping[str, Any],
    *,
    crop_shape_hw: tuple[int, int],
    runtime_cfg: Mapping[str, Any] | None = None,
) -> list[float] | None:
    """Map norm bbox from detect/overlay space onto main MP4 crop frame."""
    from frame_geometry import remap_norm_bbox_for_crop

    det_hw, overlay_hw, playback_hw = resolve_record_crop_geometry(
        detection,
        crop_shape_hw=crop_shape_hw,
        runtime_cfg=runtime_cfg,
    )
    if _bbox_stored_in_playback_space(
        detection,
        crop_shape_hw=crop_shape_hw,
        runtime_cfg=runtime_cfg,
    ):
        return [float(v) for v in bbox]
    if overlay_hw == crop_shape_hw and det_hw == overlay_hw:
        return bbox
    mapped = remap_norm_bbox_for_crop(
        bbox,
        detector_shape_hw=det_hw,
        overlay_shape_hw=overlay_hw,
        crop_shape_hw=crop_shape_hw,
        playback_shape_hw=playback_hw,
    )
    if mapped is None:
        return None
    return [float(v) for v in mapped]


def enrichment_crop_require_best_keyframe(runtime_cfg: Mapping[str, Any] | None) -> bool:
    """Linear default: crop/TG seek only from scored keyframe, not blind mid-track frame."""
    if runtime_cfg is None:
        return False
    raw = runtime_cfg.get("processor.enrichment_crop_require_keyframe")
    if raw is not None:
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw)
    return str(runtime_cfg.get("processor.pipeline_mode") or "").strip().lower() == "linear"


def pick_bbox_and_timestamp(
    detection: Mapping[str, Any],
    *,
    runtime_cfg: Mapping[str, Any] | None = None,
    require_best_keyframe: bool | None = None,
) -> tuple[list[float] | None, float]:
    """Normalized bbox + record-timeline seconds (same rules as notify preview)."""
    if require_best_keyframe is None:
        require_best_keyframe = enrichment_crop_require_best_keyframe(runtime_cfg)

    def _pick_timestamp() -> float:
        try:
            st = float(detection.get("start_time") or 0)
            et = float(detection.get("end_time") or st)
            t_mid = st + (et - st) * 0.5 if et > st else st
        except Exception:
            t_mid = 0.0
        return _apply_record_offset(float(t_mid))

    def _apply_record_offset(ts: float) -> float:
        if detection.get("playback_timeline_synced"):
            return max(0.0, float(ts))
        try:
            from dual_stream_timeline import (
                apply_record_time_offset,
                resolve_detect_record_time_offset_sec,
            )

            cam = str(detection.get("camera_id") or detection.get("triggered_camera") or "").strip()
            offset = resolve_detect_record_time_offset_sec(runtime_cfg, camera_id=cam or None)
            return apply_record_time_offset(float(ts), offset)
        except ImportError:
            return float(ts)

    key_frames = detection.get("key_frames") or []
    best_kf = None
    if isinstance(key_frames, list) and key_frames:
        dict_frames = [kf for kf in key_frames if isinstance(kf, dict)]
        if dict_frames:
            best_kf = max(dict_frames, key=lambda k: float(k.get("score") or 0.0))

    if best_kf is not None:
        bb = best_kf.get("bbox")
        bbox = None
        if isinstance(bb, (list, tuple)) and len(bb) == 4:
            try:
                bbox = [float(v) for v in bb]
            except (TypeError, ValueError):
                bbox = None
        t = _apply_record_offset(float(best_kf.get("t") or _pick_timestamp()))
        if bbox is not None:
            return bbox, float(t)
        if require_best_keyframe and isinstance(key_frames, list) and key_frames:
            return None, float(t)

    # key_frames may be stripped from notify payload (key_frame_count only); use frames.
    if require_best_keyframe and isinstance(key_frames, list) and key_frames:
        return None, float(_pick_timestamp())

    frames = detection.get("frames") or []
    mid = frames[len(frames) // 2] if isinstance(frames, list) and frames else None
    bbox = mid.get("bbox") if isinstance(mid, dict) else None
    if isinstance(mid, dict):
        t = _apply_record_offset(float(mid.get("t") or _pick_timestamp()))
    else:
        t = _pick_timestamp()
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            bbox = [float(v) for v in bbox]
        except (TypeError, ValueError):
            bbox = None
    else:
        bbox = None
    return bbox, float(t)


def _read_frame_with_retries(video_path: str, ts: float) -> np.ndarray | None:
    retry_delays = (0.2, 0.5)
    max_attempts = 1 + len(retry_delays)
    for attempt in range(max_attempts):
        if attempt > 0:
            time.sleep(retry_delays[attempt - 1])
        cap = cv2.VideoCapture(video_path)
        try:
            if not cap.isOpened():
                frame = None
            else:
                fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                if fps > 0.01:
                    n = max(0, int(ts * fps))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, n)
                else:
                    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, ts * 1000.0))
                ok_local, frame = cap.read()
                if not ok_local:
                    frame = None
                if frame is None and ts > 0:
                    cap.set(cv2.CAP_PROP_POS_MSEC, 0.0)
                    ok_local, frame = cap.read()
                    if not ok_local:
                        frame = None
            if frame is not None:
                return frame
        finally:
            cap.release()
    return None


def _crop_has_signal(crop: np.ndarray) -> bool:
    if crop is None or crop.size == 0:
        return False
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        return float(gray.std()) >= 8.0
    except Exception:
        return True


def _crop_from_frame(
    frame: np.ndarray,
    bbox: list[float],
    *,
    pad_frac: float,
) -> np.ndarray | None:
    h, w = frame.shape[:2]
    pad = max(0.0, min(0.25, float(pad_frac)))
    bw = float(bbox[2]) - float(bbox[0])
    bh = float(bbox[3]) - float(bbox[1])
    x1n = max(0.0, float(bbox[0]) - bw * pad)
    y1n = max(0.0, float(bbox[1]) - bh * pad)
    x2n = min(1.0, float(bbox[2]) + bw * pad)
    y2n = min(1.0, float(bbox[3]) + bh * pad)
    x1 = max(0, min(w - 1, int(x1n * w)))
    y1 = max(0, min(h - 1, int(y1n * h)))
    x2 = max(x1 + 1, min(w, int(x2n * w)))
    y2 = max(y1 + 1, min(h, int(y2n * h)))
    crop = frame[y1:y2, x1:x2]
    if crop.size > 0 and _crop_has_signal(crop):
        return crop
    return None


def read_record_hires_crop(
    video_path: str,
    detection: Mapping[str, Any],
    *,
    pad_frac: float | None = None,
    runtime_cfg: Mapping[str, Any] | None = None,
) -> np.ndarray | None:
    """Return BGR crop from main MP4 or None."""
    if not video_path:
        return None
    bbox, ts = pick_bbox_and_timestamp(detection, runtime_cfg=runtime_cfg)
    cam = str(detection.get("camera_id") or detection.get("triggered_camera") or "").strip()
    pad = resolve_crop_pad_frac(runtime_cfg=runtime_cfg) if pad_frac is None else max(0.0, min(0.25, float(pad_frac)))
    try:
        frame = _read_frame_with_retries(video_path, ts)
        if frame is None:
            logger.warning(
                "record_hires: video seek failed path=%s ts=%.3f camera=%s synced=%s",
                video_path,
                ts,
                cam or "?",
                bool(detection.get("playback_timeline_synced")),
            )
            return None
        crop_hw = (int(frame.shape[0]), int(frame.shape[1]))
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            logger.info(
                "record_hires: no bbox, skip full-frame fallback path=%s ts=%.3f camera=%s shape=%sx%s",
                video_path,
                ts,
                cam or "?",
                crop_hw[0],
                crop_hw[1],
            )
            return None
        bbox_list = [float(v) for v in bbox]
        det_hw, overlay_hw, playback_hw = resolve_record_crop_geometry(
            detection,
            crop_shape_hw=crop_hw,
            runtime_cfg=runtime_cfg,
        )
        playback_bbox = _bbox_stored_in_playback_space(
            detection,
            crop_shape_hw=crop_hw,
            runtime_cfg=runtime_cfg,
        )
        for extra_pad in (pad, min(0.25, pad + 0.06), min(0.25, pad + 0.12)):
            crop = _crop_from_frame(frame, bbox_list, pad_frac=extra_pad)
            if crop is not None:
                if extra_pad != pad:
                    logger.info(
                        "record_hires: playback pad retry ok camera=%s pad=%.3f",
                        cam or "?",
                        extra_pad,
                    )
                return crop
        if playback_bbox:
            logger.warning(
                "record_hires: playback bbox crop empty path=%s ts=%.3f camera=%s bbox=%s",
                video_path,
                ts,
                cam or "?",
                [round(v, 4) for v in bbox_list],
            )
            return None
        remapped = remap_bbox_for_record_crop(
            bbox_list,
            detection,
            crop_shape_hw=crop_hw,
            runtime_cfg=runtime_cfg,
        )
        if remapped is not None and remapped != bbox_list:
            crop = _crop_from_frame(frame, remapped, pad_frac=pad)
            if crop is not None:
                logger.info(
                    "record_hires: playback remap ok camera=%s overlay=%sx%s playback=%sx%s",
                    cam or "?",
                    overlay_hw[0],
                    overlay_hw[1],
                    playback_hw[0],
                    playback_hw[1],
                )
                return crop
        logger.warning(
            "record_hires: crop empty/low-signal path=%s ts=%.3f camera=%s "
            "det=%sx%s overlay=%sx%s playback=%sx%s bbox=%s remapped=%s",
            video_path,
            ts,
            cam or "?",
            det_hw[0],
            det_hw[1],
            overlay_hw[0],
            overlay_hw[1],
            playback_hw[0],
            playback_hw[1],
            [round(v, 4) for v in bbox_list],
            [round(v, 4) for v in remapped] if remapped else None,
        )
        return None
    except Exception as exc:
        logger.warning(
            "record_hires crop failed path=%s ts=%.3f camera=%s: %s",
            video_path,
            ts,
            cam or "?",
            exc,
        )
        return None


def resolve_enrichment_crop(
    detection: Mapping[str, Any],
    *,
    video_path: str | None,
    mode: str,
    lores_crop: Any = None,
    pad_frac: float | None = None,
    runtime_cfg: Mapping[str, Any] | None = None,
) -> tuple[Any, str]:
    """(crop ndarray, source tag): record_hires | best_frame_lores | none."""
    mode_norm = mode if mode in _CROP_SOURCES else "auto"
    lores = lores_crop if lores_crop is not None else detection.get("best_frame")

    if mode_norm in {"record_hires", "auto"} and video_path:
        hires = read_record_hires_crop(
            video_path,
            detection,
            pad_frac=pad_frac,
            runtime_cfg=runtime_cfg,
        )
        if hires is not None:
            return hires, "record_hires"

    if mode_norm == "record_hires":
        if isinstance(lores, np.ndarray) and lores.size > 0:
            return lores, "best_frame_lores"
        return None, "none"

    if isinstance(lores, np.ndarray) and lores.size > 0:
        return lores, "best_frame_lores"

    if mode_norm == "auto" and video_path:
        hires = read_record_hires_crop(
            video_path,
            detection,
            pad_frac=pad_frac,
            runtime_cfg=runtime_cfg,
        )
        if hires is not None:
            return hires, "record_hires"

    return None, "none"


def track_as_detection(
    track: Mapping[str, Any],
    *,
    camera_id: str | None = None,
) -> dict[str, Any]:
    return {
        "start_time": track.get("start_time"),
        "end_time": track.get("end_time"),
        "frames": track.get("frames") or [],
        "key_frames": track.get("key_frames") or [],
        "best_frame": track.get("best_frame"),
        "best_frame_score": track.get("best_frame_score"),
        "camera_id": camera_id or track.get("camera_id"),
        "playback_timeline_synced": track.get("playback_timeline_synced"),
    }
