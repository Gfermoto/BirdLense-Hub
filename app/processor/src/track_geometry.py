"""Track-level geometry: reject long-lived bbox that barely moves (feeder phantom / ByteTrack stick)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _parse_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    raw = cfg.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _parse_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    raw = cfg.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_int(cfg: Mapping[str, Any], key: str, default: int) -> int:
    raw = cfg.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class StaticPinnedTrackConfig:
    enabled: bool = True
    min_duration_sec: float = 4.0
    min_frames: int = 8
    max_center_dispersion_norm: float = 0.028
    max_bbox_iou_first_last_min: float = 0.72

    @classmethod
    def from_runtime_cfg(cls, runtime_cfg: Mapping[str, Any]) -> StaticPinnedTrackConfig:
        prefix = "processor."
        return cls(
            enabled=_parse_bool(runtime_cfg, f"{prefix}track_static_reject_enabled", True),
            min_duration_sec=_parse_float(runtime_cfg, f"{prefix}track_static_reject_min_duration_sec", 4.0),
            min_frames=_parse_int(runtime_cfg, f"{prefix}track_static_reject_min_frames", 8),
            max_center_dispersion_norm=_parse_float(
                runtime_cfg, f"{prefix}track_static_reject_max_center_dispersion_norm", 0.028
            ),
            max_bbox_iou_first_last_min=_parse_float(
                runtime_cfg, f"{prefix}track_static_reject_max_bbox_iou_first_last_min", 0.72
            ),
        )


def _bbox_center_norm(bbox: Any) -> tuple[float, float] | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def _bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def track_center_dispersion_norm(frames: list[dict[str, Any]]) -> float:
    """Max pairwise center distance in normalized frame coords (0–1 bbox space)."""
    centers: list[tuple[float, float]] = []
    for fr in frames:
        if not isinstance(fr, dict):
            continue
        c = _bbox_center_norm(fr.get("bbox"))
        if c is not None:
            centers.append(c)
    if len(centers) < 2:
        return 0.0
    max_d = 0.0
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            dx = centers[i][0] - centers[j][0]
            dy = centers[i][1] - centers[j][1]
            max_d = max(max_d, (dx * dx + dy * dy) ** 0.5)
    return max_d


def static_pinned_track_reason(track: Mapping[str, Any], cfg: StaticPinnedTrackConfig | None = None) -> str | None:
    """Return reject reason string if track looks like a frozen phantom bbox."""
    cfg = cfg or StaticPinnedTrackConfig()
    if not cfg.enabled:
        return None
    frames = [fr for fr in (track.get("frames") or []) if isinstance(fr, dict)]
    if len(frames) < cfg.min_frames:
        return None
    try:
        dur = float(track.get("end_time", 0)) - float(track.get("start_time", 0))
    except (TypeError, ValueError):
        dur = 0.0
    if dur < cfg.min_duration_sec:
        return None

    dispersion = track_center_dispersion_norm(frames)
    if dispersion > cfg.max_center_dispersion_norm:
        return None

    bboxes: list[tuple[float, float, float, float]] = []
    for fr in frames:
        bbox = fr.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                bboxes.append(tuple(float(v) for v in bbox))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
    if len(bboxes) >= 2:
        iou = _bbox_iou(bboxes[0], bboxes[-1])
        if iou < cfg.max_bbox_iou_first_last_min:
            return None

    return (
        f"rejected_static_pinned_track(disp={dispersion:.4f},dur={dur:.1f}s,"
        f"frames={len(frames)},iou_first_last>={cfg.max_bbox_iou_first_last_min:.2f})"
    )


__all__ = [
    "StaticPinnedTrackConfig",
    "static_pinned_track_reason",
    "track_center_dispersion_norm",
]
