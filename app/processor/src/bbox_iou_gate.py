"""Geometry IoU gate for detector boxes (SOTA-06)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

import numpy as np

from frame_geometry import letterbox_roundtrip_iou, xyxy_pixels_to_norm

logger = logging.getLogger(__name__)


def _cfg_float(cfg: Mapping[str, Any], key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _cfg_bool(cfg: Mapping[str, Any], key: str, default: bool) -> bool:
    raw = cfg.get(key, default)
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return bool(raw)


def apply_bbox_geometry_iou_gate(
    boxes_xyxy: np.ndarray,
    *,
    detector_shape_hw: tuple[int, int],
    overlay_shape_hw: tuple[int, int],
    runtime_cfg: Mapping[str, Any],
) -> tuple[np.ndarray, dict[str, Any], list[int]]:
    """
    Filter raw YOLO boxes failing letterbox roundtrip IoU (geometry sanity).

    Returns filtered ``boxes_xyxy`` and stats dict for metrics/logging.
    """
    stats = {
        "checked": 0,
        "passed": 0,
        "rejected_geometry_iou": 0,
        "min_roundtrip_iou": 1.0,
        "p50_roundtrip_iou": None,
    }
    if boxes_xyxy is None or len(boxes_xyxy) == 0:
        return boxes_xyxy, stats, []

    if not _cfg_bool(runtime_cfg, "detection.bbox_iou_gate_enabled", True):
        stats["passed"] = len(boxes_xyxy)
        stats["checked"] = len(boxes_xyxy)
        return boxes_xyxy, stats, list(range(len(boxes_xyxy)))

    min_iou = max(0.0, min(1.0, _cfg_float(runtime_cfg, "detection.bbox_iou_gate_min", 0.85)))
    action = str(runtime_cfg.get("detection.bbox_iou_gate_action") or "warn").strip().lower()
    reject = action == "reject"

    det_h, det_w = int(detector_shape_hw[0]), int(detector_shape_hw[1])
    src_h, src_w = int(overlay_shape_hw[0]), int(overlay_shape_hw[1])
    ious: list[float] = []
    keep_rows: list[np.ndarray] = []
    keep_indices: list[int] = []

    for idx, row in enumerate(boxes_xyxy):
        stats["checked"] += 1
        norm = xyxy_pixels_to_norm(
            (float(row[0]), float(row[1]), float(row[2]), float(row[3])),
            (det_h, det_w),
        )
        if norm is None:
            stats["rejected_geometry_iou"] += 1
            if not reject:
                keep_rows.append(row)
                keep_indices.append(idx)
                stats["passed"] += 1
            continue
        rt_iou = letterbox_roundtrip_iou(
            norm,
            source_shape_hw=(src_h, src_w),
            letterbox_shape_hw=(det_h, det_w),
        )
        ious.append(rt_iou)
        stats["min_roundtrip_iou"] = min(float(stats["min_roundtrip_iou"]), rt_iou)
        if rt_iou >= min_iou:
            keep_rows.append(row)
            keep_indices.append(idx)
            stats["passed"] += 1
        else:
            stats["rejected_geometry_iou"] += 1
            if not reject:
                keep_rows.append(row)
                keep_indices.append(idx)
                stats["passed"] += 1

    if ious:
        sorted_ious = sorted(ious)
        stats["p50_roundtrip_iou"] = round(sorted_ious[len(sorted_ious) // 2], 4)

    if stats["rejected_geometry_iou"] > 0:
        logger.warning(
            "bbox_iou_gate: rejected=%s checked=%s min_iou_thr=%.2f p50=%s action=%s",
            stats["rejected_geometry_iou"],
            stats["checked"],
            min_iou,
            stats.get("p50_roundtrip_iou"),
            action,
        )
        try:
            from processor_runtime_stats import inc_counter, set_gauge

            inc_counter("bbox_iou_gate_rejected_total", int(stats["rejected_geometry_iou"]))
            if stats.get("p50_roundtrip_iou") is not None:
                set_gauge("bbox_parity_roundtrip_iou_p50", float(stats["p50_roundtrip_iou"]))
        except Exception:
            logger.debug("bbox_iou_gate metrics publish failed", exc_info=True)

    if not keep_rows:
        return np.reshape(np.zeros((0, 4), dtype=np.float64), (-1, 4)), stats, []
    return np.stack(keep_rows, axis=0), stats, keep_indices
