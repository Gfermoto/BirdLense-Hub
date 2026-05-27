"""OpenCV motion detector with day/night profiles and MOG2 hybrid mode."""

import logging
import time
from collections import Counter

import cv2
import numpy as np

from motion_detectors.opencv_frame_motion import (
    OpenCVMotionAnalysis,
    analyze_frame_pair,
    decide_trigger_recording,
    motion_contour_polygons_normalized,
)
from motion_detectors.opencv_live_overlay import set_opencv_live_overlay
from motion_detectors.opencv_motion_mask import (
    apply_exclusion_mask,
    build_exclusion_mask,
)

logger = logging.getLogger(__name__)


class OpenCVMotionDetector:
    """
    Motion detection using frame differencing.
    Blocks in detect() until motion is found, calling capture_fn for frames.
    check_every_n_frames: analyze only every N-th frame (1 = every frame); reduces CPU at high FPS.
    """

    def __init__(
        self,
        capture_fn,
        threshold=25,
        min_contour_area=500,
        check_interval=0.12,
        check_every_n_frames=1,
        motion_max_side_px=512,
        *,
        global_motion_mean_absdiff: float = 2.5,
        min_motion_pixel_fraction: float = 0.0008,
        max_contour_area_frac: float = 0.38,
        smart_trigger_enabled: bool = True,
        detection_method: str = "frame_diff",
        suppress_warmup_frames: int = 0,
        auto_profile_enabled: bool = False,
        auto_profile_night_luma_threshold: float = 58.0,
        day_diff_threshold: int | None = None,
        day_min_contour_area: int | None = None,
        day_global_motion_mean_absdiff: float | None = None,
        day_min_motion_pixel_fraction: float | None = None,
        day_max_contour_area_frac: float | None = None,
        night_diff_threshold: int | None = None,
        night_min_contour_area: int | None = None,
        night_global_motion_mean_absdiff: float | None = None,
        night_min_motion_pixel_fraction: float | None = None,
        night_max_contour_area_frac: float | None = None,
        mog2_history: int = 300,
        mog2_var_threshold: float = 24.0,
        mog2_detect_shadows: bool = False,
        mog2_min_motion_pixel_fraction: float = 0.0006,
        mog2_min_contour_area: int | None = None,
        motion_masks: list[str] | None = None,
        min_consecutive_motion_frames: int = 2,
        scene_change_motion_fraction: float = 0.8,
        improve_contrast: bool = False,
        morphology_open_iterations: int = 1,
        camera_id: str = "",
    ):
        self.capture_fn = capture_fn
        self._camera_id = str(camera_id or "").strip()
        self.threshold = threshold
        self.min_contour_area = min_contour_area
        self.check_interval = max(0.05, float(check_interval or 0.12))
        self.check_every_n_frames = max(1, int(check_every_n_frames or 1))
        self.motion_max_side_px = max(160, int(motion_max_side_px or 512))
        self.global_motion_mean_absdiff = float(global_motion_mean_absdiff)
        self.min_motion_pixel_fraction = float(min_motion_pixel_fraction)
        self.max_contour_area_frac = float(max_contour_area_frac)
        self.smart_trigger_enabled = bool(smart_trigger_enabled)
        self.detection_method = str(detection_method or "frame_diff").strip().lower()
        if self.detection_method not in {"frame_diff", "mog2", "hybrid"}:
            self.detection_method = "frame_diff"
        self.suppress_warmup_frames = max(0, int(suppress_warmup_frames or 0))
        self.auto_profile_enabled = bool(auto_profile_enabled)
        self.auto_profile_night_luma_threshold = float(auto_profile_night_luma_threshold)
        self.day_profile = {
            "threshold": int(day_diff_threshold if day_diff_threshold is not None else threshold),
            "min_contour_area": int(day_min_contour_area if day_min_contour_area is not None else min_contour_area),
            "global_motion_mean_absdiff": float(
                day_global_motion_mean_absdiff
                if day_global_motion_mean_absdiff is not None
                else global_motion_mean_absdiff
            ),
            "min_motion_pixel_fraction": float(
                day_min_motion_pixel_fraction
                if day_min_motion_pixel_fraction is not None
                else min_motion_pixel_fraction
            ),
            "max_contour_area_frac": float(
                day_max_contour_area_frac if day_max_contour_area_frac is not None else max_contour_area_frac
            ),
        }
        self.night_profile = {
            "threshold": int(night_diff_threshold if night_diff_threshold is not None else threshold),
            "min_contour_area": int(night_min_contour_area if night_min_contour_area is not None else min_contour_area),
            "global_motion_mean_absdiff": float(
                night_global_motion_mean_absdiff
                if night_global_motion_mean_absdiff is not None
                else global_motion_mean_absdiff
            ),
            "min_motion_pixel_fraction": float(
                night_min_motion_pixel_fraction
                if night_min_motion_pixel_fraction is not None
                else min_motion_pixel_fraction
            ),
            "max_contour_area_frac": float(
                night_max_contour_area_frac if night_max_contour_area_frac is not None else max_contour_area_frac
            ),
        }
        self.mog2_min_motion_pixel_fraction = float(mog2_min_motion_pixel_fraction)
        self.mog2_min_contour_area = int(mog2_min_contour_area or min_contour_area)
        self._motion_mask_specs = [str(x).strip() for x in (motion_masks or []) if str(x).strip()]
        self._exclusion_mask: np.ndarray | None = None
        self._exclusion_mask_shape: tuple[int, int] | None = None
        self.min_consecutive_motion_frames = max(1, int(min_consecutive_motion_frames or 1))
        self.scene_change_motion_fraction = max(0.1, min(float(scene_change_motion_fraction), 0.99))
        self.improve_contrast = bool(improve_contrast)
        self.morphology_open_iterations = max(0, int(morphology_open_iterations or 0))
        self._consecutive_motion_hits = 0
        self._pending_trigger = False
        self._clahe = (
            cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) if self.improve_contrast else None
        )
        self._mog2_history = max(30, int(mog2_history or 300))
        self._mog2_var_threshold = max(4.0, float(mog2_var_threshold))
        self._mog2_detect_shadows = bool(mog2_detect_shadows)
        self._bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=self._mog2_history,
            varThreshold=self._mog2_var_threshold,
            detectShadows=self._mog2_detect_shadows,
        )
        self._prev_gray = None
        self._frame_count = 0
        self._suppressed_static_total = 0
        self._analysis_frame_count = 0
        self._reject_reasons: Counter[str] = Counter()
        self._accept_reasons: Counter[str] = Counter()
        self._last_decision_reason = "bootstrap"
        self._last_profile = "day"
        self._last_analysis: OpenCVMotionAnalysis | None = None
        self.logger = logging.getLogger(__name__)

    def _should_analyze(self):
        self._frame_count += 1
        return (self._frame_count % self.check_every_n_frames) == 0

    def _profile_name(self, gray: np.ndarray) -> str:
        if not self.auto_profile_enabled:
            return "day"
        try:
            luma = float(np.mean(gray))
        except Exception:
            luma = 255.0
        return "night" if luma < self.auto_profile_night_luma_threshold else "day"

    def _profile_cfg(self, profile: str) -> dict:
        return self.night_profile if profile == "night" else self.day_profile

    def _exclusion_mask_for(self, gray: np.ndarray) -> np.ndarray | None:
        shape = (int(gray.shape[0]), int(gray.shape[1]))
        if self._exclusion_mask_shape == shape and self._exclusion_mask is not None:
            return self._exclusion_mask
        self._exclusion_mask_shape = shape
        self._exclusion_mask = build_exclusion_mask(shape, self._motion_mask_specs)
        return self._exclusion_mask

    def _resize_gray(self, gray: np.ndarray) -> np.ndarray:
        h, w = int(gray.shape[0]), int(gray.shape[1])
        side = max(h, w)
        limit = self.motion_max_side_px
        if side <= limit:
            return gray
        scale = float(limit) / float(side)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        return cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _blur_kernel(shape: tuple[int, ...]) -> tuple[int, int]:
        side = max(int(shape[0]), int(shape[1]))
        if side <= 360:
            return (5, 5)
        if side <= 640:
            return (9, 9)
        return (15, 15)

    def _gray_from_frame(self, frame: np.ndarray, *, analyze: bool) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = self._resize_gray(gray)
        if not analyze:
            return gray
        if self._clahe is not None:
            gray = self._clahe.apply(gray)
        k = self._blur_kernel(gray.shape)
        gray = cv2.GaussianBlur(gray, k, 0)
        return gray

    def _reset_background_model(self) -> None:
        self._bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=self._mog2_history,
            varThreshold=self._mog2_var_threshold,
            detectShadows=self._mog2_detect_shadows,
        )

    def apply_opencv_trigger_config(self, opencv_cfg: dict) -> None:
        """Hot-update MOG2 / frame-diff trigger knobs without rebuilding the detector."""
        if not isinstance(opencv_cfg, dict):
            return
        method = str(opencv_cfg.get("detection_method") or self.detection_method).strip().lower()
        if method in {"frame_diff", "mog2", "hybrid"}:
            self.detection_method = method
        if "diff_threshold" in opencv_cfg:
            self.threshold = int(opencv_cfg.get("diff_threshold") or self.threshold)
        if "min_contour_area" in opencv_cfg:
            self.min_contour_area = int(opencv_cfg.get("min_contour_area") or self.min_contour_area)
        if "mog2_history" in opencv_cfg:
            self._mog2_history = max(30, int(opencv_cfg.get("mog2_history") or self._mog2_history))
        if "mog2_var_threshold" in opencv_cfg:
            self._mog2_var_threshold = max(
                4.0, float(opencv_cfg.get("mog2_var_threshold") or self._mog2_var_threshold)
            )
        if "mog2_detect_shadows" in opencv_cfg:
            self._mog2_detect_shadows = bool(opencv_cfg.get("mog2_detect_shadows"))
        if "mog2_min_contour_area" in opencv_cfg:
            self.mog2_min_contour_area = int(
                opencv_cfg.get("mog2_min_contour_area") or self.mog2_min_contour_area
            )
        if "mog2_min_motion_pixel_fraction" in opencv_cfg:
            self.mog2_min_motion_pixel_fraction = float(
                opencv_cfg.get("mog2_min_motion_pixel_fraction") or self.mog2_min_motion_pixel_fraction
            )
        self._reset_background_model()

    def _analysis_from_mog2(
        self,
        gray: np.ndarray,
        *,
        min_contour_area: int,
        exclusion_mask: np.ndarray | None,
    ) -> OpenCVMotionAnalysis:
        fg_mask = self._bg_sub.apply(gray)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        fg_mask = cv2.dilate(fg_mask, None, iterations=2)
        fg_mask = apply_exclusion_mask(fg_mask, exclusion_mask)
        motion_pixels = int(cv2.countNonZero(fg_mask))
        frame_area = max(1, int(gray.shape[0]) * int(gray.shape[1]))
        motion_frac = float(motion_pixels) / float(frame_area)
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        max_area = 0.0
        has_motion = False
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area > max_area:
                max_area = area
            if area >= int(max(1, min_contour_area)):
                has_motion = True
        fh, fw = int(gray.shape[0]), int(gray.shape[1])
        min_area = int(max(1, min_contour_area))
        overlay_min_area = max(40, min_area // 4)
        return OpenCVMotionAnalysis(
            global_mean_absdiff=float(np.mean(fg_mask) / 255.0 * 32.0),
            motion_pixel_fraction=motion_frac,
            max_contour_area=max_area,
            has_contour_motion=has_motion,
            motion_contour_polygons=motion_contour_polygons_normalized(
                contours, overlay_min_area, fh, fw
            ),
        )

    def _polygons_for_overlay(self, analysis: OpenCVMotionAnalysis) -> list[list[list[float]]]:
        out: list[list[list[float]]] = []
        for poly in analysis.motion_contour_polygons:
            out.append([[float(x), float(y)] for x, y in poly])
        return out

    @staticmethod
    def _empty_analysis() -> OpenCVMotionAnalysis:
        return OpenCVMotionAnalysis(
            global_mean_absdiff=0.0,
            motion_pixel_fraction=0.0,
            max_contour_area=0.0,
            has_contour_motion=False,
            motion_contour_polygons=(),
        )

    def _publish_live_overlay(self, analysis: OpenCVMotionAnalysis, *, profile: str) -> None:
        if not self._camera_id:
            return
        set_opencv_live_overlay(
            self._camera_id,
            {
                "trigger_polygons": self._polygons_for_overlay(analysis),
                "motion_pixel_fraction": round(float(analysis.motion_pixel_fraction), 6),
                "last_decision_reason": self._last_decision_reason,
                "profile": profile,
                "has_contour_motion": bool(analysis.has_contour_motion),
            },
        )

    def _publish_status_overlay(self, reason: str, *, analysis: OpenCVMotionAnalysis | None = None) -> None:
        if not self._camera_id:
            return
        prev_reason = self._last_decision_reason
        self._last_decision_reason = reason
        try:
            self._publish_live_overlay(
                analysis if analysis is not None else self._empty_analysis(),
                profile=self._last_profile or "day",
            )
        finally:
            self._last_decision_reason = prev_reason

    def refresh_live_overlay(self) -> None:
        """Background Live UI tick: analyze one frame without blocking detect()."""
        frame = self.capture_fn()
        if frame is None:
            self._publish_status_overlay("no_frame")
            return
        gray = self._gray_from_frame(frame, analyze=True)
        if self._prev_gray is None:
            self._prev_gray = gray
            self._publish_status_overlay("buffering_first_frame")
            return
        self._evaluate_motion(self._prev_gray, gray)
        self._prev_gray = gray

    def _evaluate_motion(self, prev_gray, gray) -> bool:
        self._analysis_frame_count += 1
        profile = self._profile_name(gray)
        self._last_profile = profile
        cfg = self._profile_cfg(profile)
        exclusion_mask = self._exclusion_mask_for(gray)
        if self.detection_method == "mog2":
            analysis = self._analysis_from_mog2(
                gray,
                min_contour_area=cfg["min_contour_area"],
                exclusion_mask=exclusion_mask,
            )
        else:
            analysis = analyze_frame_pair(
                prev_gray,
                gray,
                diff_threshold=cfg["threshold"],
                min_contour_area=cfg["min_contour_area"],
                open_iterations=self.morphology_open_iterations,
                exclusion_mask=exclusion_mask,
            )
            if self.detection_method == "hybrid":
                mog2_analysis = self._analysis_from_mog2(
                    gray,
                    min_contour_area=cfg["min_contour_area"],
                    exclusion_mask=exclusion_mask,
                )
                merged_polys = list(analysis.motion_contour_polygons)
                for poly in mog2_analysis.motion_contour_polygons:
                    if poly not in merged_polys:
                        merged_polys.append(poly)
                analysis = OpenCVMotionAnalysis(
                    global_mean_absdiff=max(analysis.global_mean_absdiff, mog2_analysis.global_mean_absdiff),
                    motion_pixel_fraction=max(analysis.motion_pixel_fraction, mog2_analysis.motion_pixel_fraction),
                    max_contour_area=max(analysis.max_contour_area, mog2_analysis.max_contour_area),
                    has_contour_motion=analysis.has_contour_motion or mog2_analysis.has_contour_motion,
                    motion_contour_polygons=tuple(merged_polys[:16]),
                )
        self._last_analysis = analysis
        if analysis.motion_pixel_fraction >= self.scene_change_motion_fraction:
            self._last_decision_reason = "scene_change_recalibrate"
            self._reject_reasons[self._last_decision_reason] += 1
            self._consecutive_motion_hits = 0
            if self.detection_method in {"mog2", "hybrid"}:
                self._reset_background_model()
            self._publish_live_overlay(analysis, profile=profile)
            return False
        if self._analysis_frame_count <= self.suppress_warmup_frames:
            self._last_decision_reason = "warmup_suppressed"
            self._reject_reasons[self._last_decision_reason] += 1
            self._consecutive_motion_hits = 0
            self._publish_live_overlay(analysis, profile=profile)
            return False
        if not self.smart_trigger_enabled:
            self._last_decision_reason = "smart_trigger_disabled"
            self._accept_reasons[self._last_decision_reason] += 1
            self._consecutive_motion_hits = self.min_consecutive_motion_frames
            self._publish_live_overlay(analysis, profile=profile)
            return True
        decision = decide_trigger_recording(
            analysis,
            frame_area=int(gray.shape[0]) * int(gray.shape[1]),
            global_motion_mean_absdiff=cfg["global_motion_mean_absdiff"],
            min_motion_pixel_fraction=max(cfg["min_motion_pixel_fraction"], self.mog2_min_motion_pixel_fraction)
            if self.detection_method == "mog2"
            else cfg["min_motion_pixel_fraction"],
            max_contour_area_frac=cfg["max_contour_area_frac"],
            profile=profile,
        )
        self._last_decision_reason = decision.reason
        if decision.triggered:
            self._consecutive_motion_hits += 1
            if self._consecutive_motion_hits >= self.min_consecutive_motion_frames:
                self._accept_reasons[decision.reason] += 1
                self._publish_live_overlay(analysis, profile=profile)
                return True
            self._last_decision_reason = "await_consecutive_frames"
            self._reject_reasons[self._last_decision_reason] += 1
            self._publish_live_overlay(analysis, profile=profile)
            return False
        self._consecutive_motion_hits = 0
        self._reject_reasons[decision.reason] += 1
        self._suppressed_static_total += 1
        self._publish_live_overlay(analysis, profile=profile)
        if self._suppressed_static_total <= 5 or self._suppressed_static_total % 120 == 0:
            self.logger.debug(
                "OpenCV motion suppressed: profile=%s reason=%s "
                "rejects=%s accepts=%s",
                profile,
                decision.reason,
                dict(self._reject_reasons),
                dict(self._accept_reasons),
            )
        return False

    def diagnostics(self) -> dict:
        return {
            "profile": self._last_profile,
            "detection_method": self.detection_method,
            "last_decision_reason": self._last_decision_reason,
            "consecutive_motion_hits": self._consecutive_motion_hits,
            "min_consecutive_motion_frames": self.min_consecutive_motion_frames,
            "motion_mask_count": len(self._motion_mask_specs),
            "motion_max_side_px": self.motion_max_side_px,
            "check_interval_seconds": self.check_interval,
            "reject_reasons": dict(self._reject_reasons),
            "accept_reasons": dict(self._accept_reasons),
        }

    def get_triggered_by(self):
        return "opencv"

    def mark_pending(self) -> None:
        """Re-arm motion when recording was deferred (e.g. min_seconds_between_recordings)."""
        self._pending_trigger = True

    def _consume_pending_trigger(self) -> bool:
        if not self._pending_trigger:
            return False
        self._pending_trigger = False
        self._last_decision_reason = "pending_requeued"
        return True

    def detect(self):
        """Block until motion detected. Returns True when motion found."""
        while True:
            if self._consume_pending_trigger():
                self.logger.debug("Motion detected (pending requeue)")
                return True
            frame = self.capture_fn()
            if frame is None:
                self._publish_status_overlay("no_frame")
                time.sleep(self.check_interval)
                continue
            analyze = self._should_analyze()
            gray = self._gray_from_frame(frame, analyze=analyze)
            if self._prev_gray is None:
                self._prev_gray = gray
                self._publish_status_overlay("buffering_first_frame")
                time.sleep(self.check_interval)
                continue
            if not analyze:
                self._prev_gray = gray
                if self._last_analysis is not None:
                    self._publish_live_overlay(self._last_analysis, profile=self._last_profile)
                time.sleep(self.check_interval)
                continue
            motion = self._evaluate_motion(self._prev_gray, gray)
            self._prev_gray = gray
            if motion:
                self.logger.debug("Motion detected")
                return True
            time.sleep(self.check_interval)

    def check(self):
        """One iteration: returns True if motion detected (for OR with Frigate)."""
        if self._consume_pending_trigger():
            self.logger.debug("Motion detected (pending requeue)")
            return True
        frame = self.capture_fn()
        if frame is None:
            self._publish_status_overlay("no_frame")
            return False
        analyze = self._should_analyze()
        gray = self._gray_from_frame(frame, analyze=analyze)
        if self._prev_gray is None:
            self._prev_gray = gray
            self._publish_status_overlay("buffering_first_frame")
            return False
        if not analyze:
            self._prev_gray = gray
            if self._last_analysis is not None:
                self._publish_live_overlay(self._last_analysis, profile=self._last_profile)
            return False
        motion = self._evaluate_motion(self._prev_gray, gray)
        self._prev_gray = gray
        if motion:
            self.logger.debug("Motion detected")
            return True
        return False
