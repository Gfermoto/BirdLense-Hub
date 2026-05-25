"""Подготовка BGR под YOLO без stretch (letterbox pad=114 как у Ultralytics/YOLOv8).

Не использует ``LetterBox`` из ultralytics: в тестах ``cv2.resize`` патчится на 2-arg
lambda без ``interpolation=``.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def _resolve_resize_interpolation() -> int:
    """Map config/env interpolation mode to cv2 constant."""
    import os
    from app_config.app_config import app_config
    import cv2

    raw = (os.environ.get("BIRDLENSE_RESIZE_INTERPOLATION") or "").strip().lower()
    if not raw:
        raw = str(app_config.get("processor.letterbox_resize_interpolation", "linear") or "linear").strip().lower()
    mapping = {
        "nearest": cv2.INTER_NEAREST,
        "linear": cv2.INTER_LINEAR,
        "cubic": cv2.INTER_CUBIC,
        "area": cv2.INTER_AREA,
        "lanczos": cv2.INTER_LANCZOS4,
    }
    return mapping.get(raw, cv2.INTER_LINEAR)


def _maybe_enhance_low_res_frame(frame: np.ndarray) -> np.ndarray:
    """Apply lightweight low-res enhancement before letterbox resize."""
    import cv2
    from app_config.app_config import app_config

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
    enhanced = cv2.addWeighted(frame, 1.0 + amount, blur, -amount, 0)
    return enhanced


def frame_matches_target_wh(
    frame: np.ndarray,
    out_wh: tuple[int, int],
    *,
    tolerance_px: int = 2,
) -> bool:
    """True when frame already matches target WxH (skip redundant resize)."""
    tw, th = int(out_wh[0]), int(out_wh[1])
    ih, iw = frame.shape[:2]
    tol = max(0, int(tolerance_px))
    return abs(iw - tw) <= tol and abs(ih - th) <= tol


def prepare_detector_frame(
    frame: np.ndarray,
    out_wh: tuple[int, int],
    *,
    skip_letterbox_when_size_matches: bool = True,
) -> np.ndarray:
    """Letterbox to ``out_wh`` unless frame is already native detect size."""
    if skip_letterbox_when_size_matches and frame_matches_target_wh(frame, out_wh):
        out = _maybe_enhance_low_res_frame(frame)
        return np.ascontiguousarray(out)
    return letterbox_bgr_to_wh(frame, out_wh)


def letterbox_bgr_to_wh(frame: np.ndarray, out_wh: tuple[int, int]) -> np.ndarray:
    """Letterbox до ``out_wh=(width,height)``. Сохраняет соотношение сторон, pad 114 BGR."""
    import cv2

    tw, th = int(out_wh[0]), int(out_wh[1])
    if tw <= 0 or th <= 0:
        raise ValueError("letterbox_bgr_to_wh: out_wh must be positive WxH")

    ih, iw = frame.shape[:2]
    frame = _maybe_enhance_low_res_frame(frame)
    r = min(tw / iw, th / ih)
    nw, nh = max(1, int(round(iw * r))), max(1, int(round(ih * r)))
    # Prefer explicit interpolation, but keep fallback for tests that monkeypatch cv2.resize with 2-arg lambda.
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
    """
    Map normalized xyxy from one frame size to another (per-axis scale).

    Used when YOLO runs on detect substream but UI plays main/record stream.
    """
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
    """xyxyn на letterbox-канвасе → xyxyn на исходном кадре (до letterbox). Для оверлея на полном видео."""
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


def prepare_yolo_detector_frame(
    frame: np.ndarray,
    runtime_cfg: Mapping[str, Any],
) -> tuple[np.ndarray, tuple[int, int], tuple[int, int]]:
    """
    Any BGR frame → detector tensor frame + shapes for bbox unmap.

    Returns ``(detector_frame, detector_shape_hw, overlay_shape_hw)``.
    Overlay shape is the coordinate space for UI/storage (native/source when available).
    """
    from pipeline_config import resolve_detector_letterbox_wh

    overlay_shape = (int(frame.shape[0]), int(frame.shape[1]))
    letterbox_wh = resolve_detector_letterbox_wh(runtime_cfg, frame.shape[:2])
    if letterbox_wh is None:
        det = np.ascontiguousarray(frame)
        return det, det.shape[:2], overlay_shape
    det = prepare_detector_frame(frame, letterbox_wh)
    return det, det.shape[:2], overlay_shape


def resolve_binary_track_imgsz(
    frame: np.ndarray,
    runtime_cfg: Mapping[str, Any],
    *,
    inference_backend: str | None = None,
    default_square: int | None = None,
) -> int | list[int]:
    """
    ``imgsz`` для YOLO ``track()`` (внутренний размер модели, не размер потока).

    Torch: при нативном letterbox-кадре — [H, W], без повторного квадрата.
    OpenVINO IR — только квадрат ``binary_imgsz`` из конфига.
    """
    from inference_lores import parse_inference_lores_wh
    from pipeline_config import resolve_binary_model_imgsz

    backend = str(
        inference_backend or runtime_cfg.get("processor.inference_backend") or "torch"
    ).strip().lower()
    square = resolve_binary_model_imgsz(
        runtime_cfg,
        default=default_square if default_square is not None else 640,
    )
    if backend == "openvino":
        return square

    try:
        det_h, det_w = int(frame.shape[0]), int(frame.shape[1])
    except (AttributeError, IndexError, TypeError, ValueError):
        det_h, det_w = 0, 0
    wh = parse_inference_lores_wh(runtime_cfg.get("processor.inference_lores_wh"))
    if det_h > 0 and det_w > 0 and wh is not None:
        tw, th = int(wh[0]), int(wh[1])
        if abs(det_w - tw) <= 2 and abs(det_h - th) <= 2 and det_w != det_h:
            return [det_h, det_w]
    return square
