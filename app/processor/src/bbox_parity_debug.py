"""Debug parity overlay: raw (green) vs accepted (red) boxes on source frame (SOTA-06)."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np

logger = logging.getLogger(__name__)

_SESSION_METRICS: dict[str, Any] = {
    "frames_saved": 0,
    "raw_boxes_total": 0,
    "accepted_boxes_total": 0,
    "mismatch_frames": 0,
    "last_saved_at": None,
}


def get_session_parity_metrics() -> dict[str, Any]:
    return dict(_SESSION_METRICS)


def reset_session_parity_metrics() -> None:
    _SESSION_METRICS.update(
        {
            "frames_saved": 0,
            "raw_boxes_total": 0,
            "accepted_boxes_total": 0,
            "mismatch_frames": 0,
            "last_saved_at": None,
        }
    )


def _parity_enabled(runtime_cfg: Mapping[str, Any]) -> bool:
    raw = runtime_cfg.get("processor.bbox_parity_debug_enabled", False)
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return bool(raw)


def _parity_dir() -> Path:
    data = (os.environ.get("DATA_DIR") or "data").strip() or "data"
    path = Path(data) / "diagnostics" / "bbox_parity"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _draw_norm_boxes(
    canvas: np.ndarray,
    boxes: list[tuple[float, float, float, float]],
    color_bgr: tuple[int, int, int],
) -> None:
    import cv2

    h, w = canvas.shape[:2]
    for box in boxes:
        if len(box) != 4:
            continue
        x1 = int(max(0, min(w - 1, round(float(box[0]) * w))))
        y1 = int(max(0, min(h - 1, round(float(box[1]) * h))))
        x2 = int(max(0, min(w - 1, round(float(box[2]) * w))))
        y2 = int(max(0, min(h - 1, round(float(box[3]) * h))))
        if x2 <= x1 or y2 <= y1:
            continue
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color_bgr, 2)


def maybe_save_parity_overlay(
    source_bgr: np.ndarray,
    *,
    raw_boxes_overlay_norm: list[tuple[float, float, float, float]],
    accepted_boxes_overlay_norm: list[tuple[float, float, float, float]],
    runtime_cfg: Mapping[str, Any],
    session_id: str | None = None,
    frame_index: int = 0,
    geometry_stats: dict[str, Any] | None = None,
) -> None:
    if not _parity_enabled(runtime_cfg):
        return
    try:
        max_frames = int(runtime_cfg.get("processor.bbox_parity_debug_max_frames") or 20)
    except (TypeError, ValueError):
        max_frames = 20
    if _SESSION_METRICS["frames_saved"] >= max(1, max_frames):
        return

    import cv2

    canvas = source_bgr.copy()
    _draw_norm_boxes(canvas, raw_boxes_overlay_norm, (0, 255, 0))
    _draw_norm_boxes(canvas, accepted_boxes_overlay_norm, (0, 0, 255))

    sid = (session_id or "live").replace("/", "_")[:64]
    out_dir = _parity_dir() / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    img_path = out_dir / f"frame_{frame_index:06d}_{ts}.jpg"
    meta_path = out_dir / f"frame_{frame_index:06d}_{ts}.json"

    cv2.imwrite(str(img_path), canvas)
    meta = {
        "frame_index": int(frame_index),
        "raw_count": len(raw_boxes_overlay_norm),
        "accepted_count": len(accepted_boxes_overlay_norm),
        "geometry_stats": geometry_stats or {},
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    _SESSION_METRICS["frames_saved"] += 1
    _SESSION_METRICS["raw_boxes_total"] += len(raw_boxes_overlay_norm)
    _SESSION_METRICS["accepted_boxes_total"] += len(accepted_boxes_overlay_norm)
    if len(raw_boxes_overlay_norm) != len(accepted_boxes_overlay_norm):
        _SESSION_METRICS["mismatch_frames"] += 1
    _SESSION_METRICS["last_saved_at"] = meta["saved_at"]
