"""Detection scheduler: bounded YOLO probe before recording (all configured triggers)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionProbeConfig:
    enabled: bool
    triggers: tuple[str, ...]
    window_seconds: float
    max_frames: int
    start_recording_on_positive: bool


def _norm_trigger(value: str | None) -> str:
    return str(value or "").strip().lower()


def build_probe_config(app_config) -> DetectionProbeConfig:
    enabled = bool(app_config.get("processor.detect_scheduler_enabled", False))
    raw = app_config.get("processor.detect_scheduler_triggers") or [
        "opencv",
        "frigate",
        "motion_sensor",
        "scales",
    ]
    if not isinstance(raw, (list, tuple, set)):
        raw = ["opencv", "frigate", "motion_sensor", "scales"]
    triggers = tuple(sorted({_norm_trigger(v) for v in raw if _norm_trigger(v)}))
    try:
        window_seconds = float(app_config.get("processor.detect_probe_window_seconds") or 2.5)
    except (TypeError, ValueError):
        window_seconds = 2.5
    try:
        max_frames = int(app_config.get("processor.detect_probe_max_frames") or 30)
    except (TypeError, ValueError):
        max_frames = 30
    start_recording_on_positive = bool(app_config.get("processor.detect_probe_start_recording_on_positive", True))
    return DetectionProbeConfig(
        enabled=enabled,
        triggers=triggers,
        window_seconds=max(0.2, min(window_seconds, 30.0)),
        max_frames=max(1, min(max_frames, 300)),
        start_recording_on_positive=start_recording_on_positive,
    )


def should_run_probe(*, trigger_source: str | None, app_config) -> bool:
    cfg = build_probe_config(app_config)
    if not cfg.enabled:
        return False
    return _norm_trigger(trigger_source) in set(cfg.triggers)
