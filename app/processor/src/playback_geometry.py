"""Playback (main/record) geometry: probe MP4/RTSP and reconcile bbox coords (Frigate-style dual-stream)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from frame_geometry import map_norm_bbox_xyxy_between_frame_shapes
from processor_runtime_stats import inc_counter

logger = logging.getLogger(__name__)


def probe_video_file_shape_hw(
    video_path: str,
    *,
    timeout_sec: float = 12.0,
) -> tuple[int, int] | None:
    """Return (height, width) from local MP4 via ffprobe, or None."""
    if not video_path:
        return None
    try:
        from stream_probe import probe_stream_ffprobe

        caps = probe_stream_ffprobe(video_path, timeout_sec=timeout_sec)
    except ImportError:
        return None
    if caps is None or caps.width <= 0 or caps.height <= 0:
        return None
    return (int(caps.height), int(caps.width))


def probe_record_stream_shape_hw(media_source: Any, *, timeout_sec: float = 10.0) -> tuple[int, int] | None:
    """Probe main record RTSP/file URL when available."""
    url = str(getattr(media_source, "stream_url", None) or "").strip()
    if not url:
        return None
    try:
        from stream_probe import probe_stream_ffprobe

        caps = probe_stream_ffprobe(url, timeout_sec=timeout_sec)
    except ImportError:
        return None
    if caps is None or caps.width <= 0 or caps.height <= 0:
        return None
    return (int(caps.height), int(caps.width))


def resolve_playback_shape_hw(
    *,
    config_main_size: tuple[int, int] | None,
    media_source: Any | None = None,
    video_path: str | None = None,
) -> tuple[tuple[int, int] | None, str]:
    """Pick playback (H,W): MP4 probe > record stream probe > config main_size."""
    if video_path:
        probed = probe_video_file_shape_hw(video_path)
        if probed is not None:
            return probed, "mp4_ffprobe"
    if media_source is not None:
        probed = probe_record_stream_shape_hw(media_source)
        if probed is not None:
            return probed, "record_stream_ffprobe"
    if config_main_size and len(config_main_size) >= 2:
        try:
            pw, ph = int(config_main_size[0]), int(config_main_size[1])
            if pw > 0 and ph > 0:
                return (ph, pw), "config_main_size"
        except (TypeError, ValueError):
            pass
    return None, "unknown"


def _shapes_equal(a: tuple[int, int] | None, b: tuple[int, int] | None) -> bool:
    if a is None or b is None:
        return False
    return int(a[0]) == int(b[0]) and int(a[1]) == int(b[1])


def _remap_bbox_list(
    bbox: Any,
    *,
    from_hw: tuple[int, int],
    to_hw: tuple[int, int],
) -> list[float] | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    mapped = map_norm_bbox_xyxy_between_frame_shapes(bbox, from_shape_hw=from_hw, to_shape_hw=to_hw)
    if mapped is None:
        return None
    return [round(float(v), 6) for v in mapped]


def remap_track_bboxes_playback_shape(
    tracks: Mapping[Any, dict[str, Any]],
    *,
    from_shape_hw: tuple[int, int],
    to_shape_hw: tuple[int, int],
) -> int:
    """Remap norm bboxes in track frames/key_frames when playback shape was wrong."""
    if _shapes_equal(from_shape_hw, to_shape_hw):
        return 0
    updated = 0
    for track in tracks.values():
        if not isinstance(track, dict):
            continue
        for frame in track.get("frames") or []:
            if not isinstance(frame, dict):
                continue
            bb = frame.get("bbox")
            new_bb = _remap_bbox_list(bb, from_hw=from_shape_hw, to_hw=to_shape_hw)
            if new_bb is not None:
                frame["bbox"] = new_bb
                updated += 1
        for kf in track.get("key_frames") or []:
            if not isinstance(kf, dict):
                continue
            bb = kf.get("bbox")
            new_bb = _remap_bbox_list(bb, from_hw=from_shape_hw, to_hw=to_shape_hw)
            if new_bb is not None:
                kf["bbox"] = new_bb
                updated += 1
    return updated


def apply_playback_shape_to_strategy(
    frame_processor: Any,
    shape_hw: tuple[int, int],
    *,
    source: str,
) -> bool:
    strategy = getattr(frame_processor, "strategy", None)
    if strategy is None or not hasattr(strategy, "set_playback_frame_shape"):
        return False
    strategy.set_playback_frame_shape(shape_hw)
    logger.info(
        "playback_shape applied source=%s shape_hw=%sx%s",
        source,
        shape_hw[0],
        shape_hw[1],
    )
    return True


def reconcile_playback_shape_after_record(
    *,
    frame_processor: Any,
    video_output: str,
    media_source: Any | None = None,
) -> dict[str, Any]:
    """After record: align playback shape to MP4; remap track bboxes if session used wrong shape."""
    summary: dict[str, Any] = {
        "mp4_shape_hw": None,
        "previous_shape_hw": None,
        "applied_shape_hw": None,
        "source": None,
        "bboxes_remapped": 0,
        "config_mismatch": False,
    }
    strategy = getattr(frame_processor, "strategy", None)
    if strategy is None:
        return summary
    prev = getattr(strategy, "_playback_frame_shape_hw", None)
    summary["previous_shape_hw"] = list(prev) if prev else None

    mp4_hw = probe_video_file_shape_hw(video_output)
    summary["mp4_shape_hw"] = list(mp4_hw) if mp4_hw else None

    config_main = getattr(media_source, "main_size", None) if media_source is not None else None
    resolved, source = resolve_playback_shape_hw(
        config_main_size=config_main,
        media_source=media_source,
        video_path=video_output if mp4_hw else None,
    )
    if resolved is None:
        return summary
    summary["source"] = source
    summary["applied_shape_hw"] = [resolved[0], resolved[1]]

    if config_main and len(config_main) >= 2:
        try:
            cfg_hw = (int(config_main[1]), int(config_main[0]))
            if not _shapes_equal(resolved, cfg_hw):
                summary["config_mismatch"] = True
                inc_counter("playback_shape_config_mismatch_total")
                inc_counter("bbox_remap_mismatch_total")
                logger.warning(
                    "playback_shape config mismatch: config=%sx%s resolved=%sx%s source=%s",
                    cfg_hw[1],
                    cfg_hw[0],
                    resolved[1],
                    resolved[0],
                    source,
                )
        except (TypeError, ValueError):
            pass

    if prev and mp4_hw and not _shapes_equal(prev, mp4_hw):
        tracks = getattr(frame_processor, "tracks", None) or {}
        remapped = remap_track_bboxes_playback_shape(tracks, from_shape_hw=prev, to_shape_hw=mp4_hw)
        summary["bboxes_remapped"] = remapped
        if remapped > 0:
            inc_counter("playback_bbox_remapped_total", remapped)
            logger.info(
                "playback_bbox remapped count=%s from=%sx%s to=%sx%s",
                remapped,
                prev[0],
                prev[1],
                mp4_hw[0],
                mp4_hw[1],
            )

    apply_playback_shape_to_strategy(frame_processor, resolved, source=source)
    return summary
