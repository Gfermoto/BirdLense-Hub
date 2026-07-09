"""Per-frame processing context (W1.2 foundation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RoiRef:
    """Reference to ROI without materialized crop copies."""

    track_id: int
    bbox_norm: tuple[float, float, float, float]
    source_shape: tuple[int, int]


@dataclass(slots=True)
class FrameContext:
    """Single frame context propagated through processor stages."""

    frame_index: int
    frame_time: float
    runtime_profile: str | None
    light_brightness: float | None
    light_contrast: float | None
    yolo_ran: bool = False
    yolo_raw_boxes: int = 0
    yolo_accepted_boxes: int = 0
    tracker_used: str | None = None
    roi_refs: list[RoiRef] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
