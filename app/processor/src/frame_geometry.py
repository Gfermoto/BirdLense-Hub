"""
Unified detector frame geometry (letterbox / native) for live and track regen (SOTA-06).

Single source of truth for canvas resolution, letterbox padding, bbox unmap/remap, and IoU checks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal, Mapping

import numpy as np

DetectorMode = Literal["live", "regen"]


def _resolve_resize_interpolation() -> int:

    import cv2

    raw = (os.environ.get("BIRDLENSE_RESIZE_INTERPOLATION") or "").strip().lower()
    if not raw:
        try:
            from app_config.app_config import app_config

            raw = str(app_config.get("processor.letterbox_resize_interpolation", "linear") or "linear").strip().lower()
        except ImportError:
            raw = "linear"
    mapping = {
        "nearest": cv2.INTER_NEAREST,
        "linear": cv2.INTER_LINEAR,
        "cubic": cv2.INTER_CUBIC,
        "area": cv2.INTER_AREA,
        "lanczos": cv2.INTER_LANCZOS4,
    }
    return mapping.get(raw, cv2.INTER_LINEAR)


def _maybe_enhance_low_res_frame(frame: np.ndarray) -> np.ndarray:
    import cv2

    try:
        from app_config.app_config import app_config
    except ImportError:
        return frame

    if not bool(app_config.get("processor.lowres_enhance_enabled", True)):
        return frame
    ih, iw = frame.shape[:2]
    max_side = int(max(iw, ih))
    max_input_px = int(app_config.get("processor.lowres_enhance_max_input_px", 800) or 800)
    if max_side > max_input_px:
        return frame
    amount = float(app_config.get("processor.lowres_sharpen_amount", 0.32) or 0.32)
    amount = max(0.0, min(1.0, amount))
    if amount <= 0.0:
        return frame
    blur = cv2.GaussianBlur(frame, (0, 0), sigmaX=1.0, sigmaY=1.0)
    return cv2.addWeighted(frame, 1.0 + amount, blur, -amount, 0)


def frame_matches_target_wh(
    frame: np.ndarray,
    out_wh: tuple[int, int],
    *,
    tolerance_px: int = 2,
) -> bool:
    tw, th = int(out_wh[0]), int(out_wh[1])
    ih, iw = frame.shape[:2]
    tol = max(0, int(tolerance_px))
    return abs(iw - tw) <= tol and abs(ih - th) <= tol


def letterbox_bgr_to_wh(frame: np.ndarray, out_wh: tuple[int, int]) -> np.ndarray:
    import cv2

    tw, th = int(out_wh[0]), int(out_wh[1])
    if tw <= 0 or th <= 0:
        raise ValueError("letterbox_bgr_to_wh: out_wh must be positive WxH")
    ih, iw = frame.shape[:2]
    frame = _maybe_enhance_low_res_frame(frame)
    r = min(tw / iw, th / ih)
    nw, nh = max(1, int(round(iw * r))), max(1, int(round(ih * r)))
    interp = _resolve_resize_interpolation()
    try:
        resized = cv2.resize(frame, (nw, nh), None, 0.0, 0.0, interp)
    except TypeError:
        resized = cv2.resize(frame, (nw, nh))
    pad_x, pad_y = tw - nw, th - nh
    top, bottom = pad_y // 2, pad_y - pad_y // 2
    left, right = pad_x // 2, pad_x - pad_x // 2
    out = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    return np.ascontiguousarray(out)


def map_norm_bbox_xyxy_between_frame_shapes(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    from_shape_hw: tuple[int, int] | list[int],
    to_shape_hw: tuple[int, int] | list[int],
) -> tuple[float, float, float, float] | None:
    if len(bbox_norm) != 4:
        return None
    try:
        fh, fw = int(from_shape_hw[0]), int(from_shape_hw[1])
        th, tw = int(to_shape_hw[0]), int(to_shape_hw[1])
    except (TypeError, ValueError, IndexError):
        return None
    if fh <= 0 or fw <= 0 or th <= 0 or tw <= 0:
        return None
    if fh == th and fw == tw:
        return (
            max(0.0, min(1.0, float(bbox_norm[0]))),
            max(0.0, min(1.0, float(bbox_norm[1]))),
            max(0.0, min(1.0, float(bbox_norm[2]))),
            max(0.0, min(1.0, float(bbox_norm[3]))),
        )
    x1 = float(bbox_norm[0]) * fw
    y1 = float(bbox_norm[1]) * fh
    x2 = float(bbox_norm[2]) * fw
    y2 = float(bbox_norm[3]) * fh
    sx = float(tw) / float(fw)
    sy = float(th) / float(fh)
    x1t, y1t, x2t, y2t = x1 * sx, y1 * sy, x2 * sx, y2 * sy
    if x2t <= x1t or y2t <= y1t:
        return None
    return (
        max(0.0, min(1.0, x1t / tw)),
        max(0.0, min(1.0, y1t / th)),
        max(0.0, min(1.0, x2t / tw)),
        max(0.0, min(1.0, y2t / th)),
    )


def unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    source_shape: tuple[int, int] | list[int],
    letterbox_shape: tuple[int, int] | list[int],
) -> tuple[float, float, float, float] | None:
    if len(bbox_norm) != 4:
        return None
    try:
        src_h, src_w = int(source_shape[0]), int(source_shape[1])
        det_h, det_w = int(letterbox_shape[0]), int(letterbox_shape[1])
    except (TypeError, ValueError, IndexError):
        return None
    if src_h <= 0 or src_w <= 0 or det_h <= 0 or det_w <= 0:
        return None
    x1d = float(bbox_norm[0]) * float(det_w)
    y1d = float(bbox_norm[1]) * float(det_h)
    x2d = float(bbox_norm[2]) * float(det_w)
    y2d = float(bbox_norm[3]) * float(det_h)
    if det_w == src_w and det_h == src_h:
        return (
            max(0.0, min(1.0, float(bbox_norm[0]))),
            max(0.0, min(1.0, float(bbox_norm[1]))),
            max(0.0, min(1.0, float(bbox_norm[2]))),
            max(0.0, min(1.0, float(bbox_norm[3]))),
        )
    r = min(float(det_w) / float(src_w), float(det_h) / float(src_h))
    if r <= 0:
        return None
    nw = float(src_w) * r
    nh = float(src_h) * r
    pad_x = (float(det_w) - nw) / 2.0
    pad_y = (float(det_h) - nh) / 2.0
    x1 = (x1d - pad_x) / r
    y1 = (y1d - pad_y) / r
    x2 = (x2d - pad_x) / r
    y2 = (y2d - pad_y) / r
    if x2 <= x1 or y2 <= y1:
        return None
    return (
        max(0.0, min(1.0, x1 / float(src_w))),
        max(0.0, min(1.0, y1 / float(src_h))),
        max(0.0, min(1.0, x2 / float(src_w))),
        max(0.0, min(1.0, y2 / float(src_h))),
    )


def resolve_binary_track_imgsz(
    frame: np.ndarray,
    runtime_cfg: Mapping[str, Any],
    *,
    inference_backend: str | None = None,
    default_square: int | None = None,
) -> int | list[int]:
    from inference_lores import parse_inference_lores_wh
    from pipeline_config import resolve_binary_model_imgsz

    backend = str(inference_backend or runtime_cfg.get("processor.inference_backend") or "torch").strip().lower()
    square = resolve_binary_model_imgsz(
        runtime_cfg,
        default=default_square if default_square is not None else 640,
    )
    try:
        det_h, det_w = int(frame.shape[0]), int(frame.shape[1])
    except (AttributeError, IndexError, TypeError, ValueError):
        det_h, det_w = 0, 0
    wh = parse_inference_lores_wh(runtime_cfg.get("processor.inference_lores_wh"))
    if (
        det_h > 0
        and det_w > 0
        and wh is not None
        and abs(det_w - int(wh[0])) <= 2
        and abs(det_h - int(wh[1])) <= 2
        and det_w != det_h
    ):
        return [det_h, det_w]
    return square


@dataclass(frozen=True)
class LetterboxMeta:
    """Letterbox transform metadata (source HxW → canvas WxH)."""

    src_hw: tuple[int, int]
    out_wh: tuple[int, int]
    scale: float
    pad_x: float
    pad_y: float
    new_w: int
    new_h: int

    @property
    def det_hw(self) -> tuple[int, int]:
        """Detector tensor shape (H, W)."""
        return (int(self.out_wh[1]), int(self.out_wh[0]))


def compute_letterbox_meta(
    source_shape_hw: tuple[int, int] | list[int],
    out_wh: tuple[int, int],
) -> LetterboxMeta | None:
    try:
        src_h, src_w = int(source_shape_hw[0]), int(source_shape_hw[1])
        tw, th = int(out_wh[0]), int(out_wh[1])
    except (TypeError, ValueError, IndexError):
        return None
    if src_h <= 0 or src_w <= 0 or tw <= 0 or th <= 0:
        return None
    if src_w == tw and src_h == th:
        return LetterboxMeta(
            src_hw=(src_h, src_w),
            out_wh=(tw, th),
            scale=1.0,
            pad_x=0.0,
            pad_y=0.0,
            new_w=src_w,
            new_h=src_h,
        )
    r = min(float(tw) / float(src_w), float(th) / float(src_h))
    if r <= 0:
        return None
    nw = max(1, int(round(float(src_w) * r)))
    nh = max(1, int(round(float(src_h) * r)))
    pad_x = (float(tw) - float(nw)) / 2.0
    pad_y = (float(th) - float(nh)) / 2.0
    return LetterboxMeta(
        src_hw=(src_h, src_w),
        out_wh=(tw, th),
        scale=r,
        pad_x=pad_x,
        pad_y=pad_y,
        new_w=nw,
        new_h=nh,
    )


def letterbox_image(frame: np.ndarray, out_wh: tuple[int, int]) -> np.ndarray:
    """Letterbox BGR frame to WxH (Ultralytics-style pad 114)."""
    return letterbox_bgr_to_wh(frame, out_wh)


def prepare_detector_frame(
    frame: np.ndarray,
    out_wh: tuple[int, int],
    *,
    skip_letterbox_when_size_matches: bool = True,
) -> np.ndarray:
    if skip_letterbox_when_size_matches and frame_matches_target_wh(frame, out_wh):
        out = _maybe_enhance_low_res_frame(frame)
        return np.ascontiguousarray(out)
    return letterbox_image(frame, out_wh)


def resolve_detector_canvas_wh(
    runtime_cfg: Mapping[str, Any],
    frame_shape: tuple[int, int] | None = None,
    *,
    mode: DetectorMode = "live",
    media_source: Any | None = None,
) -> tuple[int, int] | None:
    """
    Target letterbox canvas WxH.

    Regen uses explicit ``track_regen_lores_*`` only when set; otherwise identical to live.
    """
    from inference_lores import parse_inference_lores_wh
    from pipeline_config import resolve_detector_letterbox_wh

    if mode == "regen":
        wh = parse_inference_lores_wh(runtime_cfg.get("processor.track_regen_lores_wh"))
        if wh is not None:
            return wh
        try:
            lpx = int(runtime_cfg.get("processor.track_regen_lores_px") or 0)
        except (TypeError, ValueError):
            lpx = 0
        if lpx > 0:
            side = max(320, min(1280, lpx))
            return (side, side)
    return resolve_detector_letterbox_wh(
        runtime_cfg,
        frame_shape,
        media_source=media_source,
    )


def prepare_detector_pipeline_frame(
    frame: np.ndarray,
    runtime_cfg: Mapping[str, Any],
    *,
    mode: DetectorMode = "live",
    media_source: Any | None = None,
) -> tuple[np.ndarray, tuple[int, int], tuple[int, int], LetterboxMeta | None]:
    """
    Prepare detector input and overlay coordinate spaces (live + regen).

    Returns ``(detector_bgr, detector_shape_hw, overlay_shape_hw, letterbox_meta)``.
    """
    overlay_shape = (int(frame.shape[0]), int(frame.shape[1]))
    canvas_wh = resolve_detector_canvas_wh(
        runtime_cfg,
        overlay_shape,
        mode=mode,
        media_source=media_source,
    )
    if canvas_wh is None:
        det = np.ascontiguousarray(frame)
        meta = compute_letterbox_meta(overlay_shape, (det.shape[1], det.shape[0]))
        return det, det.shape[:2], overlay_shape, meta

    meta = compute_letterbox_meta(overlay_shape, canvas_wh)
    det = prepare_detector_frame(frame, canvas_wh)
    return det, det.shape[:2], overlay_shape, meta


def prepare_yolo_detector_frame(
    frame: np.ndarray,
    runtime_cfg: Mapping[str, Any],
    *,
    mode: DetectorMode = "live",
    media_source: Any | None = None,
) -> tuple[np.ndarray, tuple[int, int], tuple[int, int]]:
    """Backward-compatible 3-tuple API."""
    det, det_hw, overlay_hw, _meta = prepare_detector_pipeline_frame(
        frame,
        runtime_cfg,
        mode=mode,
        media_source=media_source,
    )
    return det, det_hw, overlay_hw


def unpad_boxes(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    source_shape_hw: tuple[int, int] | list[int],
    letterbox_shape_hw: tuple[int, int] | list[int],
) -> tuple[float, float, float, float] | None:
    """Normalized xyxy on letterbox canvas → normalized xyxy on source frame."""
    return unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
        bbox_norm,
        source_shape=source_shape_hw,
        letterbox_shape=letterbox_shape_hw,
    )


def pad_boxes(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    source_shape_hw: tuple[int, int] | list[int],
    letterbox_shape_hw: tuple[int, int] | list[int],
) -> tuple[float, float, float, float] | None:
    """Normalized xyxy on source → normalized xyxy on letterbox canvas."""
    if len(bbox_norm) != 4:
        return None
    try:
        src_h, src_w = int(source_shape_hw[0]), int(source_shape_hw[1])
        det_h, det_w = int(letterbox_shape_hw[0]), int(letterbox_shape_hw[1])
    except (TypeError, ValueError, IndexError):
        return None
    if src_h <= 0 or src_w <= 0 or det_h <= 0 or det_w <= 0:
        return None

    x1 = float(bbox_norm[0]) * float(src_w)
    y1 = float(bbox_norm[1]) * float(src_h)
    x2 = float(bbox_norm[2]) * float(src_w)
    y2 = float(bbox_norm[3]) * float(src_h)

    if det_w == src_w and det_h == src_h:
        return (
            max(0.0, min(1.0, float(bbox_norm[0]))),
            max(0.0, min(1.0, float(bbox_norm[1]))),
            max(0.0, min(1.0, float(bbox_norm[2]))),
            max(0.0, min(1.0, float(bbox_norm[3]))),
        )

    r = min(float(det_w) / float(src_w), float(det_h) / float(src_h))
    if r <= 0:
        return None
    nw = float(src_w) * r
    nh = float(src_h) * r
    pad_x = (float(det_w) - nw) / 2.0
    pad_y = (float(det_h) - nh) / 2.0
    x1d = x1 * r + pad_x
    y1d = y1 * r + pad_y
    x2d = x2 * r + pad_x
    y2d = y2 * r + pad_y
    if x2d <= x1d or y2d <= y1d:
        return None
    return (
        max(0.0, min(1.0, x1d / float(det_w))),
        max(0.0, min(1.0, y1d / float(det_h))),
        max(0.0, min(1.0, x2d / float(det_w))),
        max(0.0, min(1.0, y2d / float(det_h))),
    )


def scale_boxes_norm(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    from_shape_hw: tuple[int, int] | list[int],
    to_shape_hw: tuple[int, int] | list[int],
) -> tuple[float, float, float, float] | None:
    return map_norm_bbox_xyxy_between_frame_shapes(
        bbox_norm,
        from_shape_hw=from_shape_hw,
        to_shape_hw=to_shape_hw,
    )


def _shape_hw_equal(
    a: tuple[int, int] | list[int],
    b: tuple[int, int] | list[int],
) -> bool:
    try:
        return int(a[0]) == int(b[0]) and int(a[1]) == int(b[1])
    except (TypeError, ValueError, IndexError):
        return False


def remap_norm_bbox_for_crop(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    detector_shape_hw: tuple[int, int] | list[int],
    overlay_shape_hw: tuple[int, int] | list[int],
    crop_shape_hw: tuple[int, int] | list[int],
    playback_shape_hw: tuple[int, int] | list[int] | None = None,
) -> tuple[float, float, float, float] | None:
    """
    Map normalized xyxy bbox from detector letterbox canvas to crop frame (classifier/ReID).

    Dual-stream: unmap detector→detect overlay, then scale overlay→crop (main/hi-res).
    Single-stream pre-letterboxed input: when overlay==detector and crop was letterbox source,
    use letterbox unmap directly (roundtrip IoU gate).
    """
    if len(bbox_norm) != 4:
        return None
    try:
        det_h, det_w = int(detector_shape_hw[0]), int(detector_shape_hw[1])
        ov_h, ov_w = int(overlay_shape_hw[0]), int(overlay_shape_hw[1])
        cr_h, cr_w = int(crop_shape_hw[0]), int(crop_shape_hw[1])
    except (TypeError, ValueError, IndexError):
        return None
    if det_h <= 0 or det_w <= 0 or ov_h <= 0 or ov_w <= 0 or cr_h <= 0 or cr_w <= 0:
        return None

    if _shape_hw_equal(overlay_shape_hw, crop_shape_hw):
        if _shape_hw_equal(detector_shape_hw, overlay_shape_hw):
            return (
                max(0.0, min(1.0, float(bbox_norm[0]))),
                max(0.0, min(1.0, float(bbox_norm[1]))),
                max(0.0, min(1.0, float(bbox_norm[2]))),
                max(0.0, min(1.0, float(bbox_norm[3]))),
            )
        overlay_norm = unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
            bbox_norm,
            source_shape=overlay_shape_hw,
            letterbox_shape=detector_shape_hw,
        )
        return overlay_norm

    dual_stream_crop = (
        playback_shape_hw is not None
        and _shape_hw_equal(crop_shape_hw, playback_shape_hw)
        and not _shape_hw_equal(overlay_shape_hw, crop_shape_hw)
    )
    if _shape_hw_equal(overlay_shape_hw, detector_shape_hw) and not dual_stream_crop:
        direct = unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
            bbox_norm,
            source_shape=crop_shape_hw,
            letterbox_shape=detector_shape_hw,
        )
        if direct is not None:
            back = pad_boxes(
                direct,
                source_shape_hw=crop_shape_hw,
                letterbox_shape_hw=detector_shape_hw,
            )
            if back is not None and bbox_iou_norm(bbox_norm, back) >= 0.9:
                return direct
        overlay_norm = (
            max(0.0, min(1.0, float(bbox_norm[0]))),
            max(0.0, min(1.0, float(bbox_norm[1]))),
            max(0.0, min(1.0, float(bbox_norm[2]))),
            max(0.0, min(1.0, float(bbox_norm[3]))),
        )
        return map_norm_bbox_xyxy_between_frame_shapes(
            overlay_norm,
            from_shape_hw=overlay_shape_hw,
            to_shape_hw=crop_shape_hw,
        )

    overlay_norm = unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
        bbox_norm,
        source_shape=overlay_shape_hw,
        letterbox_shape=detector_shape_hw,
    )
    if overlay_norm is None:
        return None
    return map_norm_bbox_xyxy_between_frame_shapes(
        overlay_norm,
        from_shape_hw=overlay_shape_hw,
        to_shape_hw=crop_shape_hw,
    )


def bbox_iou_norm(
    a: tuple[float, ...] | list[float],
    b: tuple[float, ...] | list[float],
) -> float:
    if len(a) != 4 or len(b) != 4:
        return 0.0
    ax1, ay1, ax2, ay2 = (float(a[0]), float(a[1]), float(a[2]), float(a[3]))
    bx1, by1, bx2, by2 = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def letterbox_roundtrip_iou(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    source_shape_hw: tuple[int, int] | list[int],
    letterbox_shape_hw: tuple[int, int] | list[int],
) -> float:
    """IoU between bbox on letterbox canvas and roundtrip unmap→pad."""
    unpadded = unpad_boxes(
        bbox_norm,
        source_shape_hw=source_shape_hw,
        letterbox_shape_hw=letterbox_shape_hw,
    )
    if unpadded is None:
        return 0.0
    back = pad_boxes(
        unpadded,
        source_shape_hw=source_shape_hw,
        letterbox_shape_hw=letterbox_shape_hw,
    )
    if back is None:
        return 0.0
    return bbox_iou_norm(bbox_norm, back)


@dataclass(frozen=True)
class DetectorGeometry:
    """Live/regen coordinate spaces: overlay (detect substream) vs letterbox canvas."""

    detector_shape_hw: tuple[int, int]
    overlay_shape_hw: tuple[int, int]

    @property
    def letterbox_active(self) -> bool:
        return not _shape_hw_equal(self.detector_shape_hw, self.overlay_shape_hw)


def bbox_norm_detector_to_overlay(
    bbox_norm: tuple[float, ...] | list[float],
    *,
    geometry: DetectorGeometry,
) -> tuple[float, float, float, float] | None:
    """Normalized xyxy on detector letterbox canvas → overlay (detect stream) norm."""
    if not geometry.letterbox_active:
        if len(bbox_norm) != 4:
            return None
        return (
            max(0.0, min(1.0, float(bbox_norm[0]))),
            max(0.0, min(1.0, float(bbox_norm[1]))),
            max(0.0, min(1.0, float(bbox_norm[2]))),
            max(0.0, min(1.0, float(bbox_norm[3]))),
        )
    return unmap_letterbox_norm_xyxy_to_source_norm_xyxy(
        bbox_norm,
        source_shape=geometry.overlay_shape_hw,
        letterbox_shape=geometry.detector_shape_hw,
    )


def box_center_overlay_norm(
    crop_coords: tuple[int, int, int, int] | list[int],
    *,
    geometry: DetectorGeometry | None = None,
    frame_shape: tuple[int, int, int] | None = None,
) -> tuple[float, float]:
    """Box center in overlay-normalized coords for masks/zones (not letterbox padding)."""
    x1, y1, x2, y2 = (int(crop_coords[0]), int(crop_coords[1]), int(crop_coords[2]), int(crop_coords[3]))
    if geometry is not None and geometry.letterbox_active:
        det_h, det_w = int(geometry.detector_shape_hw[0]), int(geometry.detector_shape_hw[1])
        if det_h > 0 and det_w > 0:
            bbox_norm = (
                max(0.0, min(1.0, float(x1) / det_w)),
                max(0.0, min(1.0, float(y1) / det_h)),
                max(0.0, min(1.0, float(x2) / det_w)),
                max(0.0, min(1.0, float(y2) / det_h)),
            )
            overlay_norm = bbox_norm_detector_to_overlay(bbox_norm, geometry=geometry)
            if overlay_norm is not None:
                return (
                    (float(overlay_norm[0]) + float(overlay_norm[2])) * 0.5,
                    (float(overlay_norm[1]) + float(overlay_norm[3])) * 0.5,
                )
    if frame_shape is not None and len(frame_shape) >= 2:
        fh, fw = int(frame_shape[0]), int(frame_shape[1])
        if fh > 0 and fw > 0:
            return ((float(x1) + float(x2)) * 0.5 / fw, (float(y1) + float(y2)) * 0.5 / fh)
    return (0.5, 0.5)


def xyxy_pixels_to_norm(
    xyxy: tuple[float, float, float, float],
    shape_hw: tuple[int, int],
) -> tuple[float, float, float, float] | None:
    try:
        h, w = int(shape_hw[0]), int(shape_hw[1])
    except (TypeError, ValueError, IndexError):
        return None
    if h <= 0 or w <= 0:
        return None
    x1, y1, x2, y2 = (float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3]))
    if x2 <= x1 or y2 <= y1:
        return None
    return (
        max(0.0, min(1.0, x1 / w)),
        max(0.0, min(1.0, y1 / h)),
        max(0.0, min(1.0, x2 / w)),
        max(0.0, min(1.0, y2 / h)),
    )


def live_regen_canvas_parity(
    frame: np.ndarray,
    runtime_cfg: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare live vs regen canvas resolution + letterbox meta on the same frame."""
    live_wh = resolve_detector_canvas_wh(runtime_cfg, frame.shape[:2], mode="live")
    regen_wh = resolve_detector_canvas_wh(runtime_cfg, frame.shape[:2], mode="regen")
    live_meta = compute_letterbox_meta(frame.shape[:2], live_wh) if live_wh else None
    regen_meta = compute_letterbox_meta(frame.shape[:2], regen_wh) if regen_wh else None
    return {
        "live_canvas_wh": list(live_wh) if live_wh else None,
        "regen_canvas_wh": list(regen_wh) if regen_wh else None,
        "canvas_wh_match": live_wh == regen_wh,
        "live_meta": live_meta.__dict__ if live_meta else None,
        "regen_meta": regen_meta.__dict__ if regen_meta else None,
        "meta_match": live_meta == regen_meta,
    }
