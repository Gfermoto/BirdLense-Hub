"""Unified tracking policy for Live and Regen (SOTA-11)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from app_config.app_config import app_config
from pipeline_policy import build_pipeline_policy_snapshot
from tracker_low_fps import resolve_adaptive_tracker_path
from tracker_registry import resolve_tracker_preset

_LOG = logging.getLogger(__name__)
Mode = Literal["live", "regen"]


def _cfg_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    try:
        raw = cfg.get(key)
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _cfg_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    raw = cfg.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _cfg_optional_float(cfg: Mapping[str, Any], key: str) -> float | None:
    try:
        raw = cfg.get(key)
        if raw is None:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def unified_with_live_pipeline(cfg: Mapping[str, Any] | None = None) -> bool:
    """When True, regen uses the same thresholds/scope/geometry as live."""
    c = cfg if cfg is not None else (app_config.config or {})
    return _cfg_bool(c, "processor.track_regen_match_live_pipeline", True)


@dataclass
class UnifiedTrackingPolicy:
    """Single source of truth for ByteTrack + post-track filters."""

    mode: Mode
    unified_with_live: bool
    stream_fps: float
    source_fps: float
    frame_step: int
    geometry_mode: Mode
    for_track_regen: bool
    base_tracker: str
    min_track_duration: float
    min_confidence_to_process: float | None
    min_confidence_to_store: float | None
    min_confidence_binary_override: float | None = None
    min_confidence_binary_bird_override: float | None = None
    iou_id_fallback: bool = False
    iou_match_threshold: float = 0.20
    binary_only: bool = False
    skip_light_gate: bool = False
    regional_species_override: list[str] | None = None
    pipeline_policy: dict[str, Any] = field(default_factory=dict)

    def effective_stream_fps(self) -> float:
        if self.stream_fps > 0.5:
            return float(self.stream_fps)
        if self.source_fps > 0.5 and self.frame_step > 1:
            return float(self.source_fps) / float(self.frame_step)
        return float(self.source_fps) if self.source_fps > 0.5 else 0.0

    def session_context(self) -> dict[str, Any]:
        eff = self.effective_stream_fps()
        return {
            "stream_fps": eff,
            "source_fps": float(self.source_fps),
            "frame_step": int(self.frame_step),
            "tracking_mode": self.mode,
            "tracking_unified_with_live": bool(self.unified_with_live),
        }

    def resolve_tracker_path(self, profile_tracker: str | None = None) -> str:
        """FPS buckets + adaptive MOG2 buffer (SOTA-10)."""
        picked = resolve_tracker_preset(profile_tracker or self.base_tracker)
        cfg = app_config.config or {}
        raw = cfg.get("processor.tracker_fps_profiles") or {}
        fps = self.effective_stream_fps()
        if isinstance(raw, dict) and fps > 0:
            for key, limit in (
                ("lte_5", 5.0),
                ("lte_7", 7.0),
                ("lte_10", 10.0),
                ("lte_15", 15.0),
            ):
                name = str(raw.get(key) or "").strip()
                if name and fps <= limit:
                    picked = resolve_tracker_preset(name)
                    break
            else:
                gt = str(raw.get("gt_15") or "").strip()
                if gt and fps > 15.0:
                    picked = resolve_tracker_preset(gt)
        return resolve_adaptive_tracker_path(picked, fps)

    def geometry_mode_for_frame(self) -> Mode:
        return self.geometry_mode

    @property
    def use_regen_direct_track_call(self) -> bool:
        """Regen-only Ultralytics track() without retry; off when unified with live."""
        return bool(self.for_track_regen and not self.unified_with_live and self.iou_id_fallback)


def build_unified_tracking_policy(
    runtime_cfg: Mapping[str, Any] | None,
    *,
    mode: Mode,
    stream_fps: float = 0.0,
    source_fps: float = 0.0,
    frame_step: int = 1,
    regional_species_override: list[str] | None = None,
    strategy_override: str | None = None,
    min_center_dist_override: float | None = None,
) -> UnifiedTrackingPolicy:
    cfg = dict(runtime_cfg or app_config.config or {})
    unified = unified_with_live_pipeline(cfg) if mode == "regen" else True
    frame_step = max(1, int(frame_step or 1))
    src_fps = float(source_fps or stream_fps or 0.0)
    eff_fps = float(stream_fps or 0.0)
    if eff_fps <= 0.5 and src_fps > 0.5:
        eff_fps = src_fps / float(frame_step) if frame_step > 1 else src_fps

    base_tracker = str(cfg.get("processor.tracker") or "bytetrack.yaml").strip() or "bytetrack.yaml"
    live_min_track = _cfg_float(cfg, "processor.min_track_duration", 0.6)
    live_min_proc = _cfg_optional_float(cfg, "processor.min_confidence_to_process")
    live_store = _cfg_optional_float(cfg, "detection.min_confidence_to_store")

    if unified:
        min_track = live_min_track
        min_proc = live_min_proc
        min_store = live_store
        geometry_mode: Mode = "live"
        iou_fb = _cfg_bool(cfg, "processor.iou_id_fallback_live_enabled", True)
        iou_thr = _cfg_float(cfg, "processor.iou_id_fallback_live_match_threshold", 0.20)
        bin_override = None
        bird_override = None
        binary_only = False
        reg_override = regional_species_override
    else:
        min_track = _cfg_optional_float(cfg, "processor.track_regen_min_track_duration")
        if min_track is None:
            min_track = live_min_track
        min_proc = _cfg_optional_float(cfg, "processor.track_regen_min_confidence_to_process")
        if min_proc is None:
            min_proc = live_min_proc
        min_store = _cfg_optional_float(cfg, "processor.track_regen_decision_detector_store_floor")
        if min_store is None:
            min_store = live_store
        geometry_mode = "regen"
        iou_fb = _cfg_bool(cfg, "processor.track_regen_iou_id_fallback", True)
        iou_thr = _cfg_float(cfg, "processor.track_regen_iou_match_threshold", 0.22)
        bin_override = _cfg_optional_float(cfg, "processor.track_regen_min_confidence_binary")
        bird_override = _cfg_optional_float(cfg, "processor.track_regen_min_confidence_binary_bird")
        binary_only = _cfg_bool(cfg, "processor.track_regen_binary_only", False)
        if _cfg_bool(cfg, "processor.track_regen_ignore_regional_species", True):
            reg_override = [] if regional_species_override is None else regional_species_override
        else:
            reg_override = regional_species_override

    policy = UnifiedTrackingPolicy(
        mode=mode,
        unified_with_live=bool(unified),
        stream_fps=eff_fps,
        source_fps=src_fps,
        frame_step=frame_step,
        geometry_mode=geometry_mode,
        for_track_regen=mode == "regen",
        base_tracker=base_tracker,
        min_track_duration=float(min_track),
        min_confidence_to_process=min_proc,
        min_confidence_to_store=min_store,
        min_confidence_binary_override=bin_override,
        min_confidence_binary_bird_override=bird_override,
        iou_id_fallback=bool(iou_fb),
        iou_match_threshold=float(iou_thr),
        binary_only=bool(binary_only) and mode == "regen",
        skip_light_gate=mode == "regen",
        regional_species_override=reg_override,
        pipeline_policy=build_pipeline_policy_snapshot(
            app_config,
            for_track_regen=mode == "regen",
            strategy_override=strategy_override,
            regional_species_override=reg_override,
            min_center_dist_override=min_center_dist_override,
        ),
    )
    return policy


def attach_tracking_policy_to_strategy(strategy: Any, policy: UnifiedTrackingPolicy) -> None:
    strategy._tracking_policy = policy
    strategy._for_track_regen = bool(policy.for_track_regen)


def apply_policy_profile_overrides(
    profile_overrides: dict[str, Any],
    policy: UnifiedTrackingPolicy,
) -> dict[str, Any]:
    out = dict(profile_overrides or {})
    if policy.min_confidence_binary_override is not None:
        regen_val = float(policy.min_confidence_binary_override)
        existing = out.get("min_confidence_binary")
        try:
            existing_f = float(existing) if existing is not None else None
        except (TypeError, ValueError):
            existing_f = None
        out["min_confidence_binary"] = (
            min(regen_val, existing_f) if existing_f is not None else regen_val
        )
    if policy.min_confidence_binary_bird_override is not None:
        regen_val = float(policy.min_confidence_binary_bird_override)
        existing = out.get("min_confidence_binary_bird")
        try:
            existing_f = float(existing) if existing is not None else None
        except (TypeError, ValueError):
            existing_f = None
        out["min_confidence_binary_bird"] = (
            min(regen_val, existing_f) if existing_f is not None else regen_val
        )
    return out
