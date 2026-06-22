"""Stream geometry mapping utilities for BirdLense Hub.

Provides coordinate space transformations between detector streams, letterboxed frames,
and analysis targets. Integrates with frame_geometry for consistent geometry handling.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Literal, Tuple
from .frame_geometry import (
    DetectorGeometry,
    DetectorMode,
    frame_matches_target_wh,
    letterbox_bgr_to_wh,
    map_norm_bbox_xyxy_between_frame_shapes,
    resolve_detector_canvas_wh,
)

# Stream-specific constants
STREAM_MODE_LIVE = "live"
STREAM_MODE_REGEN = "regen"


def get_stream_canvas_wh(
    runtime_cfg: dict[str, Any],
    frame_shape: Tuple[int, int] | None = None,
    *,
    mode: str = STREAM_MODE_LIVE,
    media_source: Any | None = None,
) -> Tuple[int, int] | None:
    """Determine target canvas dimensions for stream processing.

    Args:
        runtime_cfg: Configuration dictionary containing stream settings
        frame_shape: Optional (height, width) tuple for current frame
        mode: Stream mode ("live" or "regen")
        media_source: Optional media source identifier

    Returns:
        Target canvas dimensions as (width, height) tuple, or None
    """
    if mode == STREAM_MODE_REGEN:
        from .inference_lores import parse_inference_lores_wh
        wh = parse_inference_lores_wh(runtime_cfg.get("processor.track_regen_lores_wh"))
        if wh is not None:
            return wh
        try:
            lpx = int(runtime_cfg.get("processor.track_regen_lores_px") or 0)
            if lpx > 0:
                side = max(320, min(1280, lpx))
                return (side, side)
        except (TypeError, ValueError):
            pass
    
    return resolve_detector_canvas_wh(
        runtime_cfg, 
        frame_shape, 
        mode=mode, 
        media_source=media_source,
    )


def map_stream_bbox(
    bbox_norm: Tuple[float, ...] | list[float],
    *,
    source_wh: Tuple[int, int] | list[int],
    target_wh: Tuple[int, int] | list[int],
    geometry: DetectorGeometry | None = None,
) -> Tuple[float, float, float, float] | None:
    """Map normalized bounding box between stream geometry spaces.

    Handles letterboxing and coordinate transformations between:
    - Detector letterbox canvas → overlay space (detect stream)
    - Overlay space → analysis target (e.g., crop, classification)

    Args:
        bbox_norm: Normalized xyxy bbox [x1, y1, x2, y2] in [0, 1] range
        source_wh: Source frame dimensions (height, width)
        target_wh: Target frame dimensions (height, width)
        geometry: Optional DetectorGeometry for complex transformations

    Returns:
        Mapped normalized bbox in target coordinates, or None if invalid
    """
    if len(bbox_norm) != 4:
        return None
    
    try:
        # Handle direct mapping when no geometry specified
        if geometry is None and frame_matches_target_wh(bbox_norm, target_wh):
            return bbox_norm
            
        # Use frame_geometry utilities for complex transformations
        if geometry is None:
            return map_norm_bbox_xyxy_between_frame_shapes(
                bbox_norm, 
                from_shape_hw=source_wh, 
                to_shape_hw=target_wh
            )
            
        # Handle letterboxed geometry transformations
        if geometry.letterbox_active:
            return unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
                bbox_norm, 
                source_shape=geometry.overlay_shape_hw, 
                letterbox_shape=geometry.detector_shape_hw,
            )
            
        return map_norm_bbox_xyxy_between_frame_shapes(
            bbox_norm, 
            from_shape_hw=source_wh, 
            to_shape_hw=target_wh
        )
        
    except (TypeError, ValueError, IndexError):
        return None


def apply_stream_letterbox(
    frame: np.ndarray, 
    out_wh: Tuple[int, int], 
    *,
    skip_letterbox_when_size_matches: bool = True,
) -> np.ndarray:
    """Apply letterbox transformation to stream frame.

    Args:
        frame: Input frame (BGR format)
        out_wh: Target canvas dimensions (width, height)
        skip_letterbox_when_size_matches: Skip letterboxing if frame matches target size

    Returns:
        Letterboxed frame ready for stream processing
    """
    if skip_letterbox_when_size_matches and frame_matches_target_wh(frame, out_wh):
        return frame
    return letterbox_bgr_to_wh(frame, out_wh)


def resolve_stream_canvas(
    runtime_cfg: dict[str, Any],
    frame_shape: Tuple[int, int] | None = None,
    *,
    mode: str = STREAM_MODE_LIVE,
) -> Tuple[int, int] | None:
    """Resolve target canvas dimensions with stream mode awareness.

    Args:
        runtime_cfg: Configuration dictionary
        frame_shape: Optional (height, width) tuple
        mode: Stream mode ("live" or "regen")

    Returns:
        Target canvas dimensions or None
    """
    if mode == STREAM_MODE_REGEN:
        return get_stream_canvas_wh(
            runtime_cfg, 
            frame_shape, 
            mode=STREAM_MODE_REGEN,
        )
    return get_stream_canvas_wh(
        runtime_cfg, 
        frame_shape, 
        mode=STREAM_MODE_LIVE,
    )


def prepare_detector_frame_for_stream(
    frame: np.ndarray,
    runtime_cfg: dict[str, Any],
    *,
    mode: str = STREAM_MODE_LIVE,
) -> Tuple[np.ndarray, Tuple[int, int], Tuple[int, int]]:
    """Prepare frame for detector processing with stream-aware geometry.

    Args:
        frame: Input frame
        runtime_cfg: Configuration dictionary
        mode: Stream mode ("live" or "regen")

    Returns:
        (processed_frame, detector_shape, overlay_shape)
    """
    overlay_shape = (int(frame.shape[0]), int(frame.shape[1]))
    canvas_wh = resolve_stream_canvas(
        runtime_cfg, 
        frame_shape, 
        mode=mode,
    )
    
    if canvas_wh is None:
        return frame, overlay_shape, overlay_shape
    
    processed_frame = apply_stream_letterbox(
        frame, 
        canvas_wh, 
        skip_letterbox_when_size_matches=True,
    )
    detector_shape = canvas_wh  # Simplified for stream context
    return processed_frame, detector_shape, overlay_shape