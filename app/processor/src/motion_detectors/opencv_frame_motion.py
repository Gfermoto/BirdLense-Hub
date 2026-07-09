"""Shared OpenCV frame-diff analysis for motion triggers and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class OpenCVMotionAnalysis:
    """Result of comparing two consecutive grayscale frames."""

    global_mean_absdiff: float
    motion_pixel_fraction: float
    max_contour_area: float
    has_contour_motion: bool
    motion_contour_polygons: tuple[tuple[tuple[float, float], ...], ...] = ()


@dataclass(frozen=True)
class OpenCVTriggerDecision:
    """Structured trigger decision with reason for telemetry/audit."""

    triggered: bool
    reason: str
    profile: str = "day"


def motion_contour_polygons_normalized(
    contours,
    min_contour_area: int,
    frame_h: int,
    frame_w: int,
    *,
    max_polygons: int = 16,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Axis-aligned contour boxes as normalized 4-point polygons for UI overlay."""
    fw = max(1, int(frame_w))
    fh = max(1, int(frame_h))
    min_area = max(1, int(min_contour_area))
    polys: list[tuple[tuple[float, float], ...]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 2 or h < 2:
            continue
        polys.append(
            (
                (x / fw, y / fh),
                ((x + w) / fw, y / fh),
                ((x + w) / fw, (y + h) / fh),
                (x / fw, (y + h) / fh),
            )
        )
        if len(polys) >= max_polygons:
            break
    return tuple(polys)


def analyze_frame_pair(
    prev_gray: np.ndarray,
    gray: np.ndarray,
    *,
    diff_threshold: int,
    min_contour_area: int,
    dilate_iterations: int = 2,
    open_iterations: int = 1,
    exclusion_mask: np.ndarray | None = None,
) -> OpenCVMotionAnalysis:
    """Frame diff + contour stats (no side effects)."""
    diff = cv2.absdiff(prev_gray, gray)
    global_mean = float(np.mean(diff))
    thresh = cv2.threshold(diff, int(diff_threshold), 255, cv2.THRESH_BINARY)[1]
    if open_iterations > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(
            thresh,
            cv2.MORPH_OPEN,
            kernel,
            iterations=int(open_iterations),
        )
    if dilate_iterations > 0:
        thresh = cv2.dilate(thresh, None, iterations=int(dilate_iterations))
    if exclusion_mask is not None:
        from motion_detectors.opencv_motion_mask import apply_exclusion_mask

        thresh = apply_exclusion_mask(thresh, exclusion_mask)
    motion_pixels = int(cv2.countNonZero(thresh))
    frame_area = max(1, int(gray.shape[0]) * int(gray.shape[1]))
    motion_frac = float(motion_pixels) / float(frame_area)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    max_area = 0.0
    has_motion = False
    min_area = max(1, int(min_contour_area))
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area > max_area:
            max_area = area
        if area >= min_area:
            has_motion = True
    fh, fw = int(gray.shape[0]), int(gray.shape[1])
    overlay_min_area = max(40, min_area // 4)
    return OpenCVMotionAnalysis(
        global_mean_absdiff=global_mean,
        motion_pixel_fraction=motion_frac,
        max_contour_area=max_area,
        has_contour_motion=has_motion,
        motion_contour_polygons=motion_contour_polygons_normalized(contours, overlay_min_area, fh, fw),
    )


def should_trigger_recording(
    analysis: OpenCVMotionAnalysis,
    *,
    frame_area: int,
    global_motion_mean_absdiff: float = 2.5,
    min_motion_pixel_fraction: float = 0.0008,
    max_contour_area_frac: float = 0.38,
) -> bool:
    """
    Decide whether OpenCV motion should start a recording session.

    - Rejects compression/AE flicker: low global diff and tiny changed-pixel fraction.
    - Rejects dominant static structure (feeder body / machine): contour covers a large
      fraction of the frame with no global scene motion.
    - Accepts localized motion (typical bird) or whole-frame motion (wind, visitor).
    """
    if not analysis.has_contour_motion:
        return False
    area = max(1, int(frame_area))
    if analysis.max_contour_area / float(area) > float(max_contour_area_frac):
        if analysis.global_mean_absdiff < float(global_motion_mean_absdiff):
            return False
    if analysis.global_mean_absdiff >= float(global_motion_mean_absdiff):
        return True
    return analysis.motion_pixel_fraction >= float(min_motion_pixel_fraction)


def decide_trigger_recording(
    analysis: OpenCVMotionAnalysis,
    *,
    frame_area: int,
    global_motion_mean_absdiff: float = 2.5,
    min_motion_pixel_fraction: float = 0.0008,
    max_contour_area_frac: float = 0.38,
    profile: str = "day",
) -> OpenCVTriggerDecision:
    """Like ``should_trigger_recording`` but returns a reject/accept reason."""
    if not analysis.has_contour_motion:
        return OpenCVTriggerDecision(False, "no_contour_motion", profile=profile)
    area = max(1, int(frame_area))
    contour_frac = analysis.max_contour_area / float(area)
    if contour_frac > float(max_contour_area_frac) and analysis.global_mean_absdiff < float(global_motion_mean_absdiff):
        return OpenCVTriggerDecision(False, "static_dominant_blob", profile=profile)
    if analysis.global_mean_absdiff >= float(global_motion_mean_absdiff):
        return OpenCVTriggerDecision(True, "global_motion", profile=profile)
    if analysis.motion_pixel_fraction >= float(min_motion_pixel_fraction):
        return OpenCVTriggerDecision(True, "local_motion_fraction", profile=profile)
    return OpenCVTriggerDecision(False, "insufficient_motion_fraction", profile=profile)
