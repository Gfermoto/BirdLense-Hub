"""Playback (main/record) geometry: probe MP4/RTSP and reconcile bbox coords (Frigate-style dual-stream)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from frame_geometry import map_norm_bbox_xyxy_between_frame_shapes
from processor_runtime_stats import inc_counter
from shared.frame_shape import (
    metadata_hw_list,
    parse_metadata_hw,
    probe_wh,
    wh_to_hw,
)

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
    if caps is None:
        return None
    wh = probe_wh(caps.main_size)
    if wh is None:
        return None
    return wh_to_hw(wh)


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
    if caps is None:
        return None
    wh = probe_wh(caps.main_size)
    if wh is None:
        return None
    return wh_to_hw(wh)


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
        cfg_wh = probe_wh(config_main_size)
        if cfg_wh is not None:
            return wh_to_hw(cfg_wh), "config_main_size"
    return None, "unknown"


def assert_playback_metadata_consistent(
    *,
    playback_shape_hw: tuple[int, int] | list[int] | None,
    main_size_wh: tuple[int, int] | None,
    mp4_shape_hw: tuple[int, int] | None = None,
    context: str = "persist",
) -> bool:
    """Validate metadata [H,W] against MP4 probe or main_size (W,H)."""
    playback_hw = parse_metadata_hw(playback_shape_hw)
    if playback_hw is None:
        return True
    reference_hw = mp4_shape_hw
    if reference_hw is None and main_size_wh is not None:
        cfg_wh = probe_wh(main_size_wh)
        if cfg_wh is not None:
            reference_hw = wh_to_hw(cfg_wh)
    if reference_hw is None:
        return True
    if playback_hw != reference_hw:
        inc_counter("geometry_metadata_invalid_total")
        logger.warning(
            "geometry metadata mismatch context=%s playback=%sx%s reference=%sx%s main_size=%s",
            context,
            playback_hw[0],
            playback_hw[1],
            reference_hw[0],
            reference_hw[1],
            main_size_wh,
        )
        return False
    return True


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
    main_size_wh: tuple[int, int] | None = None,
) -> bool:
    strategy = getattr(frame_processor, "strategy", None)
    if strategy is None or not hasattr(strategy, "set_playback_frame_shape"):
        return False
    assert_playback_metadata_consistent(
        playback_shape_hw=shape_hw,
        main_size_wh=main_size_wh,
        mp4_shape_hw=shape_hw if source == "mp4_ffprobe" else None,
        context="apply_playback_shape",
    )
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
        cfg_wh = probe_wh(config_main)
        if cfg_wh is not None:
            cfg_hw = wh_to_hw(cfg_wh)
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

    apply_playback_shape_to_strategy(
        frame_processor,
        resolved,
        source=source,
        main_size_wh=probe_wh(config_main) if config_main else None,
    )
    return summary


def detection_geometry_metadata_from_strategy(strategy: Any | None) -> dict[str, list[int]]:
    """Shape metadata for persisted detection rows (record_hires / notify remap)."""
    if strategy is None:
        return {}
    meta: dict[str, list[int]] = {}
    det = getattr(strategy, "_detector_frame_shape", None)
    overlay = getattr(strategy, "_overlay_frame_shape", None)
    playback = getattr(strategy, "_playback_frame_shape_hw", None)
    if det is not None and len(det) >= 2:
        meta["detector_shape_hw"] = metadata_hw_list((int(det[0]), int(det[1])))
    if overlay is not None and len(overlay) >= 2:
        meta["overlay_shape_hw"] = metadata_hw_list((int(overlay[0]), int(overlay[1])))
    if playback is not None and len(playback) >= 2:
        meta["playback_shape_hw"] = metadata_hw_list((int(playback[0]), int(playback[1])))
    return meta


def _resolve_main_size_wh(frame_processor: Any | None) -> tuple[int, int] | None:
    if frame_processor is None:
        return None
    media_source = getattr(frame_processor, "media_source", None)
    if media_source is None:
        return None
    main_size = getattr(media_source, "main_size", None)
    if main_size is None:
        return None
    wh = probe_wh(main_size)
    return wh


def enrich_detections_playback_geometry(
    detections: list[dict[str, Any]],
    frame_processor: Any | None,
    *,
    mp4_shape_hw: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    """Attach detector/overlay/playback shapes so record_hires skips lores fallback."""
    strategy = getattr(frame_processor, "strategy", None) if frame_processor is not None else None
    meta = detection_geometry_metadata_from_strategy(strategy)
    main_size_wh = _resolve_main_size_wh(frame_processor)
    if meta:
        assert_playback_metadata_consistent(
            playback_shape_hw=meta.get("playback_shape_hw"),
            main_size_wh=main_size_wh,
            mp4_shape_hw=mp4_shape_hw,
            context="finalize_enrich",
        )
    if not meta:
        return detections
    enriched: list[dict[str, Any]] = []
    for row in detections:
        if not isinstance(row, dict):
            enriched.append(row)
            continue
        patched = dict(row)
        for key, val in meta.items():
            if patched.get(key) is None:
                patched[key] = list(val)
        assert_playback_metadata_consistent(
            playback_shape_hw=patched.get("playback_shape_hw"),
            main_size_wh=main_size_wh,
            mp4_shape_hw=mp4_shape_hw,
            context="finalize_row",
        )
        enriched.append(patched)
    return enriched
