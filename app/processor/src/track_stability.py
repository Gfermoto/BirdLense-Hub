"""Low-FPS track stability metrics (SOTA-10): ID switches and track duration."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _bbox_xyxy_norm(bbox: Sequence[float] | None) -> tuple[float, float, float, float] | None:
    if not bbox or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


class TrackStabilityMonitor:
    """Detect geometric ID switches between consecutive YOLO frames."""

    def __init__(self, *, iou_threshold: float = 0.25) -> None:
        self.iou_threshold = max(0.05, float(iou_threshold))
        self.track_id_switches_count = 0
        self._prev_by_id: dict[int, tuple[float, float, float, float]] = {}

    def reset(self) -> None:
        self.track_id_switches_count = 0
        self._prev_by_id = {}

    def observe_detections(self, detections: Sequence[Any] | None) -> None:
        if not detections:
            self._prev_by_id = {}
            return
        curr: dict[int, tuple[float, float, float, float]] = {}
        for det in detections:
            try:
                tid = int(getattr(det, "track_id", 0) or 0)
            except (TypeError, ValueError):
                continue
            if tid <= 0:
                continue
            box = _bbox_xyxy_norm(getattr(det, "bbox", None))
            if box is None:
                continue
            curr[tid] = box

        if not self._prev_by_id:
            self._prev_by_id = curr
            return

        matched_prev: set[int] = set()
        for tid, box in curr.items():
            best_pid = None
            best_iou = 0.0
            for pid, pbox in self._prev_by_id.items():
                if pid in matched_prev:
                    continue
                iou = bbox_iou(box, pbox)
                if iou > best_iou:
                    best_iou = iou
                    best_pid = pid
            if (
                best_pid is not None
                and best_iou >= self.iou_threshold
                and best_pid != tid
                and best_pid not in curr
            ):
                self.track_id_switches_count += 1
            if best_pid is not None and best_iou >= self.iou_threshold:
                matched_prev.add(best_pid)

        self._prev_by_id = curr


def summarize_tracks_stability(
    tracks: Mapping[int | str, Any] | None,
    *,
    stream_fps: float,
    id_switches_increment: int = 0,
) -> dict[str, float | int]:
    """Aggregate track duration from FrameProcessor.tracks + frame-level switches."""
    fps = float(stream_fps) if stream_fps > 0.5 else 7.0
    durations_sec: list[float] = []
    if tracks:
        for tr in tracks.values():
            if not isinstance(tr, dict):
                continue
            frames = tr.get("frames")
            if not isinstance(frames, list) or len(frames) < 2:
                continue
            try:
                t0 = float(frames[0].get("t") or 0.0)
                t1 = float(frames[-1].get("t") or t0)
            except (TypeError, ValueError, AttributeError):
                continue
            dur = max(0.0, t1 - t0)
            if dur <= 0:
                dur = max(1, len(frames) - 1) / fps
            durations_sec.append(dur)

    avg_sec = sum(durations_sec) / len(durations_sec) if durations_sec else 0.0
    return {
        "track_id_switches_count": int(id_switches_increment),
        "avg_track_duration_sec": round(avg_sec, 4),
        "avg_track_duration_frames": round(avg_sec * fps, 3) if fps > 0 else 0.0,
        "tracks_with_duration_samples": len(durations_sec),
    }
