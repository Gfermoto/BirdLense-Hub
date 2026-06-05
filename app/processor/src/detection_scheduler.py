"""Detection scheduler: wake detector first; recording starts only from confirmed track."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionProbeConfig:
    enabled: bool
    triggers: tuple[str, ...]
    window_seconds: float
    max_frames: int
    min_hits: int
    start_recording_on_positive: bool


@dataclass(frozen=True)
class DetectFirstConfig:
    enabled: bool
    triggers: tuple[str, ...]
    window_seconds: float
    max_frames: int
    confirm_min_hits: int
    confirm_min_track_seconds: float


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
    try:
        min_hits = int(app_config.get("processor.detect_probe_min_hits") or 2)
    except (TypeError, ValueError):
        min_hits = 2
    return DetectionProbeConfig(
        enabled=enabled,
        triggers=triggers,
        window_seconds=max(0.2, min(window_seconds, 30.0)),
        max_frames=max(1, min(max_frames, 300)),
        min_hits=max(1, min(min_hits, 10)),
        start_recording_on_positive=start_recording_on_positive,
    )


def build_detect_first_config(app_config) -> DetectFirstConfig:
    raw_enabled = app_config.get("processor.detect_first_enabled")
    enabled = bool(app_config.get("processor.detect_scheduler_enabled", True)) if raw_enabled is None else bool(raw_enabled)
    raw = app_config.get("processor.detect_first_triggers") or app_config.get("processor.detect_scheduler_triggers") or [
        "opencv",
        "frigate",
        "motion_sensor",
        "scales",
    ]
    if not isinstance(raw, (list, tuple, set)):
        raw = ["opencv", "frigate", "motion_sensor", "scales"]
    triggers = tuple(sorted({_norm_trigger(v) for v in raw if _norm_trigger(v)}))
    try:
        window_seconds = float(
            app_config.get("processor.detect_first_window_seconds")
            or app_config.get("processor.detect_probe_window_seconds")
            or 2.5
        )
    except (TypeError, ValueError):
        window_seconds = 2.5
    try:
        max_frames = int(
            app_config.get("processor.detect_first_max_frames")
            or app_config.get("processor.detect_probe_max_frames")
            or 30
        )
    except (TypeError, ValueError):
        max_frames = 30
    try:
        confirm_min_hits = int(
            app_config.get("processor.detect_first_confirm_min_hits")
            or app_config.get("processor.detect_probe_min_hits")
            or 2
        )
    except (TypeError, ValueError):
        confirm_min_hits = 2
    try:
        confirm_min_track_seconds = float(
            app_config.get("processor.detect_first_confirm_min_track_seconds")
            or app_config.get("processor.min_track_duration")
            or 0.5
        )
    except (TypeError, ValueError):
        confirm_min_track_seconds = 0.5
    return DetectFirstConfig(
        enabled=enabled,
        triggers=triggers,
        window_seconds=max(0.2, min(window_seconds, 30.0)),
        max_frames=max(1, min(max_frames, 300)),
        confirm_min_hits=max(1, min(confirm_min_hits, 10)),
        confirm_min_track_seconds=max(0.0, min(confirm_min_track_seconds, 30.0)),
    )


def trigger_requires_detect_first(
    cfg: DetectFirstConfig,
    trigger_source: str | None,
    app_config,
) -> bool:
    """Whether this trigger must pass lores YOLO+track before main record."""
    trigger = _norm_trigger(trigger_source)
    if not trigger:
        return False
    if trigger == "opencv" and bool(app_config.get("detection.track_first_gate_enabled", True)):
        return True
    return trigger in set(cfg.triggers)


def is_valid_detect_first_anchor(anchor: dict | None) -> bool:
    """Confirmed lores anchor with track id and normalized bbox."""
    if not isinstance(anchor, dict) or anchor.get("detect_first_bypassed"):
        return False
    if anchor.get("track_id") is None:
        return False
    bbox = anchor.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    try:
        coords = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return False
    if not all(0.0 <= v <= 1.0 for v in coords):
        return False
    return coords[2] > coords[0] and coords[3] > coords[1]


def requires_detect_first_before_record(*, args, app_config) -> bool:
    """Go2RTC live: lores detect+track gate before FFmpeg touches main stream."""
    if args is not None and getattr(args, "input", None):
        return False
    source = (app_config.get("video.source") or "go2rtc").strip().lower()
    return source == "go2rtc"


def should_run_probe(*, trigger_source: str | None, app_config) -> bool:
    cfg = build_probe_config(app_config)
    if not cfg.enabled:
        return False
    trigger = _norm_trigger(trigger_source)
    # Track-first: OpenCV must confirm YOLO bird even if legacy user_config omits opencv.
    if trigger == "opencv" and bool(app_config.get("detection.track_first_gate_enabled", True)):
        return True
    return trigger in set(cfg.triggers)


def should_run_detect_first(*, trigger_source: str | None, app_config) -> bool:
    if requires_detect_first_before_record(args=None, app_config=app_config):
        return bool(_norm_trigger(trigger_source))
    cfg = build_detect_first_config(app_config)
    if not cfg.enabled:
        return False
    return trigger_requires_detect_first(cfg, trigger_source, app_config)
