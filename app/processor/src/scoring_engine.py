"""SOTA 2.0 unified bird scoring — replaces independent filter cascade when enabled."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

import cv2
import numpy as np

from scene_adaptive import SceneAdaptiveAnalyzer, SceneAdaptiveConfig

logger = logging.getLogger(__name__)


class DecisionZone(str, Enum):
    ACCEPT = "accept"
    REVIEW = "review"
    REJECT = "reject"


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _parse_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None or not isinstance(raw, (str, int, float)):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_int(cfg: Mapping[str, Any], key: str, default: int) -> int:
    try:
        raw = cfg.get(key)
    except (AttributeError, TypeError):
        return default
    if raw is None or not isinstance(raw, (str, int, float)):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class ScoringEngineConfig:
    enabled: bool = True
    weight_conf: float = 0.45
    weight_motion: float = 0.25
    weight_shape: float = 0.15
    weight_background: float = 0.15
    frigate_prior_boost: float = 0.20
    default_low_threshold: float = 0.38
    default_high_threshold: float = 0.52
    review_band_width: float = 0.14
    calibration_frames: int = 60
    calibration_max_noise_rate: float = 0.01
    calibration_percentile: float = 0.95
    giant_box_area_frac: float = 0.5
    scene: SceneAdaptiveConfig = field(default_factory=SceneAdaptiveConfig)

    @classmethod
    def from_runtime_cfg(cls, runtime_cfg: Mapping[str, Any]) -> ScoringEngineConfig:
        return cls(
            enabled=_parse_bool(runtime_cfg, "processor.scoring_engine_enabled", False),
            weight_conf=_parse_float(runtime_cfg, "processor.scoring_weight_conf", 0.45),
            weight_motion=_parse_float(runtime_cfg, "processor.scoring_weight_motion", 0.25),
            weight_shape=_parse_float(runtime_cfg, "processor.scoring_weight_shape", 0.15),
            weight_background=_parse_float(runtime_cfg, "processor.scoring_weight_background", 0.15),
            frigate_prior_boost=_parse_float(runtime_cfg, "processor.scoring_frigate_prior_boost", 0.20),
            default_low_threshold=_parse_float(runtime_cfg, "processor.scoring_default_low_threshold", 0.38),
            default_high_threshold=_parse_float(runtime_cfg, "processor.scoring_default_high_threshold", 0.52),
            review_band_width=_parse_float(runtime_cfg, "processor.scoring_review_band_width", 0.14),
            calibration_frames=max(10, _parse_int(runtime_cfg, "processor.scoring_calibration_frames", 60)),
            calibration_max_noise_rate=_parse_float(runtime_cfg, "processor.scoring_calibration_max_noise_rate", 0.01),
            calibration_percentile=_parse_float(runtime_cfg, "processor.scoring_calibration_percentile", 0.95),
            giant_box_area_frac=_parse_float(runtime_cfg, "processor.scoring_giant_box_area_frac", 0.5),
            scene=SceneAdaptiveConfig.from_runtime_cfg(runtime_cfg),
        )


@dataclass
class ScoreBreakdown:
    raw_conf: float
    motion_score: float
    bg_score: float
    shape_score: float
    weighted_score: float
    frigate_boost: float
    final_score: float


@dataclass
class ScoringDecision:
    zone: DecisionZone
    breakdown: ScoreBreakdown
    reject_reason: str | None = None


@dataclass
class CalibrationState:
    frame_count: int = 0
    calibrated: bool = False
    low_threshold: float = 0.38
    high_threshold: float = 0.52
    noise_scores: deque = field(default_factory=lambda: deque(maxlen=120))

    def snapshot(self) -> dict[str, float | int | bool]:
        return {
            "frame_count": self.frame_count,
            "calibrated": self.calibrated,
            "low_threshold": self.low_threshold,
            "high_threshold": self.high_threshold,
            "noise_samples": len(self.noise_scores),
        }


class ScoringEngine:
    """Unified P(bird) scorer with scene auto-calibration."""

    def __init__(self, cfg: ScoringEngineConfig | None = None) -> None:
        self.cfg = cfg or ScoringEngineConfig()
        self._scene = SceneAdaptiveAnalyzer(self.cfg.scene)
        self._prev_gray: np.ndarray | None = None
        self._calibration = CalibrationState(
            low_threshold=float(self.cfg.default_low_threshold),
            high_threshold=float(self.cfg.default_high_threshold),
        )
        self.last_stats: dict[str, int] = {
            "scoring_accepted": 0,
            "scoring_review": 0,
            "scoring_rejected": 0,
            "scoring_giant_reject": 0,
        }
        self.last_decisions: list[dict[str, Any]] = []

    def reset(self) -> None:
        self._scene.reset()
        self._prev_gray = None
        self._calibration = CalibrationState(
            low_threshold=float(self.cfg.default_low_threshold),
            high_threshold=float(self.cfg.default_high_threshold),
        )
        self.last_stats = {k: 0 for k in self.last_stats}
        self.last_decisions = []

    @property
    def calibration(self) -> CalibrationState:
        return self._calibration

    def _box_aspect(self, box: dict[str, Any]) -> float:
        x1, y1, x2, y2 = [int(v) for v in box["crop_coords"]]
        bw = max(1.0, float(x2 - x1))
        bh = max(1.0, float(y2 - y1))
        return bw / bh

    def _shape_score(self, box: dict[str, Any]) -> float:
        ar = self._box_aspect(box)
        conf = float(box.get("conf") or 0.0)
        # Square-ish compact blobs at low conf → low shape score (phantom-like).
        if 0.85 <= ar <= 1.18 and conf < 0.55:
            return max(0.0, 0.35 - abs(ar - 1.0) * 0.5)
        if ar <= 0.75 or ar >= 1.35:
            return min(1.0, 0.55 + conf * 0.35)
        return min(1.0, 0.45 + conf * 0.4)

    def _motion_score(
        self,
        box: dict[str, Any],
        *,
        prev_gray: np.ndarray | None,
        gray: np.ndarray,
    ) -> float:
        if prev_gray is None or prev_gray.shape != gray.shape:
            return 0.5
        x1, y1, x2, y2 = [int(v) for v in box["crop_coords"]]
        roi_prev = prev_gray[y1:y2, x1:x2]
        roi_curr = gray[y1:y2, x1:x2]
        if roi_prev.size < 64 or roi_curr.size < 64:
            return 0.5
        diff = float(np.mean(cv2.absdiff(roi_curr, roi_prev)))
        score = float(np.clip(diff / 24.0, 0.0, 1.0))
        conf = float(box.get("conf") or 0.0)
        if conf >= 0.48 and score < 0.25:
            score = max(score, 0.38)
        return score

    def _bg_score(self, box: dict[str, Any], frame_shape: tuple[int, int, int]) -> float:
        conf = float(box.get("conf") or 0.0)
        if not self._scene.last_state.warmed_up:
            return float(np.clip(0.30 + conf * 0.45, 0.0, 1.0))
        ratio = self._scene.box_foreground_ratio(box, frame_shape)
        if ratio is None:
            return float(np.clip(0.28 + conf * 0.42, 0.0, 1.0))
        raw = float(np.clip(ratio / max(0.05, self.cfg.scene.bg_min_foreground_ratio), 0.0, 1.0))
        if conf >= 0.45 and raw < 0.35:
            return max(raw, 0.36)
        return raw

    def compute_breakdown(
        self,
        box: dict[str, Any],
        *,
        frame_bgr: np.ndarray,
        frigate_prior_active: bool = False,
    ) -> ScoreBreakdown:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        conf = float(np.clip(float(box.get("conf") or 0.0), 0.0, 1.0))
        motion = self._motion_score(box, prev_gray=self._prev_gray, gray=gray)
        bg = self._bg_score(box, frame_bgr.shape)
        shape = self._shape_score(box)
        w = self.cfg
        weighted = w.weight_conf * conf + w.weight_motion * motion + w.weight_background * bg + w.weight_shape * shape
        frigate_boost = w.frigate_prior_boost if frigate_prior_active else 0.0
        final = float(np.clip(weighted + frigate_boost, 0.0, 1.0))
        return ScoreBreakdown(
            raw_conf=conf,
            motion_score=motion,
            bg_score=bg,
            shape_score=shape,
            weighted_score=weighted,
            frigate_boost=frigate_boost,
            final_score=final,
        )

    def _observe_calibration(self, score: float, *, had_bird_candidate: bool) -> None:
        cal = self._calibration
        cal.frame_count += 1
        if not had_bird_candidate:
            cal.noise_scores.append(score)
        if not cal.calibrated and cal.frame_count >= self.cfg.calibration_frames:
            if cal.noise_scores:
                arr = np.array(list(cal.noise_scores), dtype=np.float64)
                p = float(np.percentile(arr, self.cfg.calibration_percentile * 100.0))
                cal.low_threshold = float(
                    np.clip(
                        max(p + 0.02, self.cfg.default_low_threshold * 0.85),
                        0.25,
                        0.75,
                    )
                )
                cal.high_threshold = float(
                    np.clip(
                        cal.low_threshold + self.cfg.review_band_width,
                        cal.low_threshold + 0.05,
                        0.92,
                    )
                )
                cal.calibrated = True
                logger.info(
                    "ScoringEngine auto-calibration: low=%.3f high=%.3f samples=%s frames=%s",
                    cal.low_threshold,
                    cal.high_threshold,
                    len(cal.noise_scores),
                    cal.frame_count,
                )
            return

    def decide(
        self,
        box: dict[str, Any],
        *,
        frame_bgr: np.ndarray,
        frigate_prior_active: bool = False,
    ) -> ScoringDecision:
        area_norm = float(box.get("box_area_norm") or 0.0)
        if area_norm > self.cfg.giant_box_area_frac:
            bd = self.compute_breakdown(box, frame_bgr=frame_bgr, frigate_prior_active=frigate_prior_active)
            return ScoringDecision(
                zone=DecisionZone.REJECT,
                breakdown=bd,
                reject_reason=f"phantom_box_giant_area(area_norm={area_norm:.3f})",
            )

        bd = self.compute_breakdown(box, frame_bgr=frame_bgr, frigate_prior_active=frigate_prior_active)
        cal = self._calibration
        if bd.final_score >= cal.high_threshold:
            zone = DecisionZone.ACCEPT
            reason = None
        elif bd.final_score >= cal.low_threshold:
            zone = DecisionZone.REVIEW
            reason = f"review_band(score={bd.final_score:.3f},low={cal.low_threshold:.3f})"
        else:
            zone = DecisionZone.REJECT
            reason = f"score_below_low_threshold({bd.final_score:.3f}<{cal.low_threshold:.3f})"

        return ScoringDecision(zone=zone, breakdown=bd, reject_reason=reason)

    def filter_boxes(
        self,
        boxes: list[dict[str, Any]],
        *,
        frame_bgr: np.ndarray,
        frame_index: int,
        frigate_prior_active: bool = False,
    ) -> list[dict[str, Any]]:
        self.last_stats = {k: 0 for k in self.last_stats}
        self.last_decisions = []
        self._scene.update(frame_bgr)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        bird_boxes = [b for b in boxes if str(b.get("detector_label") or "") == "Bird"]
        max_score = 0.0
        for box in bird_boxes:
            bd = self.compute_breakdown(box, frame_bgr=frame_bgr, frigate_prior_active=frigate_prior_active)
            max_score = max(max_score, bd.final_score)

        self._observe_calibration(max_score, had_bird_candidate=bool(bird_boxes))

        kept: list[dict[str, Any]] = []
        for box in boxes:
            label = str(box.get("detector_label") or "")
            if label != "Bird":
                kept.append(box)
                continue
            decision = self.decide(
                box,
                frame_bgr=frame_bgr,
                frigate_prior_active=frigate_prior_active,
            )
            trace = {
                "frame_index": frame_index,
                "track_id": int(box.get("track_id") or 0),
                "raw_conf": decision.breakdown.raw_conf,
                "motion_score": decision.breakdown.motion_score,
                "bg_score": decision.breakdown.bg_score,
                "shape_score": decision.breakdown.shape_score,
                "weighted_score": decision.breakdown.weighted_score,
                "frigate_boost": decision.breakdown.frigate_boost,
                "final_score": decision.breakdown.final_score,
                "final_decision": decision.zone.value,
                "reject_reason": decision.reject_reason,
                "low_threshold": self._calibration.low_threshold,
                "high_threshold": self._calibration.high_threshold,
                "calibrated": self._calibration.calibrated,
            }
            self.last_decisions.append(trace)
            if decision.zone == DecisionZone.ACCEPT:
                kept.append(box)
                self.last_stats["scoring_accepted"] += 1
            elif decision.zone == DecisionZone.REVIEW:
                box = dict(box)
                box["scoring_review_only"] = True
                kept.append(box)
                self.last_stats["scoring_review"] += 1
            else:
                self.last_stats["scoring_rejected"] += 1
                if decision.reject_reason and "giant" in decision.reject_reason:
                    self.last_stats["scoring_giant_reject"] += 1

        self._prev_gray = gray
        try:
            from scoring_telemetry import get_scoring_telemetry
        except ImportError:
            logger.debug("scoring telemetry module unavailable", exc_info=True)
        else:
            get_scoring_telemetry().record_decisions(
                self.last_decisions,
                stats=self.last_stats,
            )
            get_scoring_telemetry().record_calibration(self._calibration.snapshot())
        return kept
