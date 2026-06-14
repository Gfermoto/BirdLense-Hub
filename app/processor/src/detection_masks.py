"""NVR-style ignore masks and zones of interest (normalized polygon coords)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def _parse_polygons(raw: Any) -> list[list[tuple[float, float]]]:
    if not raw or not isinstance(raw, (list, tuple)):
        return []
    out: list[list[tuple[float, float]]] = []
    for poly in raw:
        if not isinstance(poly, (list, tuple)) or len(poly) < 3:
            continue
        pts: list[tuple[float, float]] = []
        for p in poly:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                pts.append((float(p[0]), float(p[1])))
        if len(pts) >= 3:
            out.append(pts)
    return out


@dataclass
class DetectionMaskConfig:
    ignore_masks: list[list[tuple[float, float]]]
    interest_zones: list[list[tuple[float, float]]]
    interest_zones_required: bool = False

    @classmethod
    def from_runtime_cfg(cls, runtime_cfg: Mapping[str, Any]) -> DetectionMaskConfig:
        return cls(
            ignore_masks=_parse_polygons(runtime_cfg.get("processor.detection_ignore_masks")),
            interest_zones=_parse_polygons(runtime_cfg.get("processor.detection_interest_zones")),
            interest_zones_required=bool(runtime_cfg.get("processor.detection_interest_zones_required", False)),
        )


def _point_in_polygon(px: float, py: float, poly: Sequence[tuple[float, float]]) -> bool:
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _box_center_norm(
    box: dict[str, Any],
    fw: int,
    fh: int,
    *,
    geometry: Any | None = None,
) -> tuple[float, float]:
    from frame_geometry import box_center_overlay_norm

    coords = box.get("crop_coords")
    if coords is None:
        return (0.5, 0.5)
    return box_center_overlay_norm(
        coords,
        geometry=geometry,
        frame_shape=(fh, fw, 3),
    )


class DetectionMaskFilter:
    def __init__(self, cfg: DetectionMaskConfig | None = None) -> None:
        self.cfg = cfg or DetectionMaskConfig([], [], False)

    def reject_reason(
        self,
        box: dict[str, Any],
        *,
        frame_shape: tuple[int, int, int],
        geometry: Any | None = None,
    ) -> str | None:
        if not self.cfg.ignore_masks and not self.cfg.interest_zones:
            return None
        fh, fw = frame_shape[:2]
        cx, cy = _box_center_norm(box, fw, fh, geometry=geometry)
        for poly in self.cfg.ignore_masks:
            if _point_in_polygon(cx, cy, poly):
                return f"ignore_mask_hit(cx={cx:.3f},cy={cy:.3f})"
        if self.cfg.interest_zones_required and self.cfg.interest_zones:
            if not any(_point_in_polygon(cx, cy, z) for z in self.cfg.interest_zones):
                return f"outside_interest_zone(cx={cx:.3f},cy={cy:.3f})"
        return None
