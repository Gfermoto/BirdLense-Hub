"""Dynamic pipeline sizing: camera resolution, model imgsz, stream FPS — no magic 704/7."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from inference_lores import LoResSize, parse_inference_lores_wh, resolve_inference_lores_size

try:
    from stream_probe import StreamCapabilities, get_stream_capabilities
except ImportError:
    StreamCapabilities = None  # type: ignore[misc, assignment]
    get_stream_capabilities = None  # type: ignore[assignment]

# YOLO export square size when config omits processor.binary_imgsz (not stream resolution).
DEFAULT_MODEL_IMGSZ = 640
# Mirrors default_config.yaml processor.detection_quality_assumed_fps (last resort for FPS only).
DEFAULT_ASSUMED_FPS_CONFIG_KEY = "processor.detection_quality_assumed_fps"


def _cfg_get(cfg: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """``processor.foo`` dot key or nested ``{"processor": {"foo": ...}}``."""
    if cfg is None:
        return default
    raw = cfg.get(key)
    if raw is not None:
        return raw
    parts = key.split(".")
    cur: Any = cfg
    for part in parts:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool = False) -> bool:
    raw = _cfg_get(cfg, key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _parse_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    raw = _cfg_get(cfg, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def detect_use_native_resolution(cfg: Mapping[str, Any]) -> bool:
    """True: capture/detector use camera frame size; model imgsz is internal only."""
    return _parse_bool(cfg, "processor.detect_use_native_resolution", default=False)


def resolve_binary_model_imgsz(
    runtime_cfg: Mapping[str, Any],
    *,
    default: int = DEFAULT_MODEL_IMGSZ,
) -> int:
    """Square ``imgsz`` for YOLO export (ONNX/torch), not stream resolution."""
    try:
        raw = _cfg_get(runtime_cfg, "processor.binary_imgsz")
        if raw is not None:
            return max(320, int(raw))
    except (TypeError, ValueError):
        pass
    return max(320, int(default))


def resolve_detector_letterbox_wh(
    runtime_cfg: Mapping[str, Any],
    frame_shape: tuple[int, int] | None = None,
    *,
    media_source: Any | None = None,
) -> LoResSize | None:
    """
    Target WxH for letterbox before YOLO, or None to use frame as-is.

    ``detect_use_native_resolution`` → None;
    else ``inference_lores_wh`` / ``inference_lores_px``;
    else frame / stream probe (not global record resolution).
    """
    if detect_use_native_resolution(runtime_cfg):
        return None
    wh = parse_inference_lores_wh(_cfg_get(runtime_cfg, "processor.inference_lores_wh"))
    if wh is not None:
        return wh
    try:
        lpx = int(_cfg_get(runtime_cfg, "processor.inference_lores_px") or 0)
    except (TypeError, ValueError):
        lpx = 0
    if lpx > 0:
        side = max(320, min(1280, lpx))
        return (side, side)
    if frame_shape and len(frame_shape) >= 2:
        h, w = int(frame_shape[0]), int(frame_shape[1])
        if w > 0 and h > 0:
            return (max(320, min(1280, w)), max(320, min(1280, h)))
    if get_stream_capabilities is not None and media_source is not None:
        caps = get_stream_capabilities(media_source)
        if caps is not None and caps.width > 0 and caps.height > 0:
            return (
                max(320, min(1280, int(caps.width))),
                max(320, min(1280, int(caps.height))),
            )
    return resolve_inference_lores_size(runtime_cfg)


def resolve_stream_fps(
    media_source: Any | None,
    runtime_cfg: Mapping[str, Any],
) -> float:
    """
    Effective FPS: StreamCapabilities > source attrs > ``video.detect_fps`` > assumed_fps config.
    """
    if get_stream_capabilities is not None and media_source is not None:
        caps = get_stream_capabilities(media_source)
        if caps is not None and caps.fps > 0.5:
            return float(caps.fps)
    if media_source is not None:
        for attr in ("source_fps", "_source_fps"):
            try:
                fps = float(getattr(media_source, attr, 0) or 0)
            except (TypeError, ValueError):
                fps = 0.0
            if fps > 0.5:
                return fps
    cfg_fps = _parse_float(runtime_cfg, "video.detect_fps", 0.0)
    if cfg_fps > 0.5:
        return cfg_fps
    assumed = _parse_float(runtime_cfg, DEFAULT_ASSUMED_FPS_CONFIG_KEY, 0.0)
    if assumed <= 0.5:
        assumed = 1.0
    return max(1.0, assumed)


def resolve_detection_quality_fps(
    runtime_cfg: Mapping[str, Any],
    media_source: Any | None = None,
) -> float:
    return resolve_stream_fps(media_source, runtime_cfg)


@dataclass(frozen=True)
class MotionTriggerContext:
    """Passed from motion layer into recording/detector for logging and scoring hints."""

    triggered_by: str
    stream_fps: float
    detector_letterbox_wh: LoResSize | None
    model_imgsz: int
    use_native_resolution: bool

    def as_dict(self) -> dict[str, Any]:
        wh = self.detector_letterbox_wh
        return {
            "triggered_by": self.triggered_by,
            "stream_fps": round(float(self.stream_fps), 3),
            "detector_letterbox_wh": list(wh) if wh else None,
            "model_imgsz": int(self.model_imgsz),
            "detect_use_native_resolution": bool(self.use_native_resolution),
        }


def build_motion_trigger_context(
    motion_detector: Any,
    runtime_cfg: Mapping[str, Any],
    *,
    media_source: Any | None = None,
    frame_shape: tuple[int, int] | None = None,
) -> MotionTriggerContext:
    triggered_by = ""
    fn = getattr(motion_detector, "get_triggered_by", None)
    if callable(fn):
        triggered_by = str(fn() or "").strip().lower()
    return MotionTriggerContext(
        triggered_by=triggered_by,
        stream_fps=resolve_stream_fps(media_source, runtime_cfg),
        detector_letterbox_wh=resolve_detector_letterbox_wh(
            runtime_cfg,
            frame_shape,
            media_source=media_source,
        ),
        model_imgsz=resolve_binary_model_imgsz(runtime_cfg),
        use_native_resolution=detect_use_native_resolution(runtime_cfg),
    )
