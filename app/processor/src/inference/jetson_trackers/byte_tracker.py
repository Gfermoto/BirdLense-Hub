"""Vendored ByteTrack (Ultralytics AGPL) — subset for Jetson TensorRT detector."""

from typing import List, Tuple

import numpy as np

try:
    import lap  # noqa: F401

    _HAS_LAP = True
except ImportError:
    _HAS_LAP = False


def _iou_batch(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    a = a[:, None, :]
    b = b[None, :, :]
    xx1 = np.maximum(a[..., 0], b[..., 0])
    yy1 = np.maximum(a[..., 1], b[..., 1])
    xx2 = np.minimum(a[..., 2], b[..., 2])
    yy2 = np.minimum(a[..., 3], b[..., 3])
    inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
    area_a = (a[..., 2] - a[..., 0]) * (a[..., 3] - a[..., 1])
    area_b = (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1])
    return inter / np.maximum(area_a + area_b - inter, 1e-6)


class BYTETracker:
    """Minimal ByteTrack for BirdLense Jetson TRT path."""

    def __init__(
        self,
        track_thresh: float = 0.2,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
    ) -> None:
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer
        self.frame_id = 0
        self._tracks: List[dict] = []
        self._next_id = 1

    def reset(self) -> None:
        self.frame_id = 0
        self._tracks = []
        self._next_id = 1

    def update(self, dets: np.ndarray, img_info: Tuple[int, int], _img_size: Tuple[int, int]) -> np.ndarray:
        self.frame_id += 1
        if dets is None or len(dets) == 0:
            self._tracks = [t for t in self._tracks if self.frame_id - t["last"] <= self.track_buffer]
            return np.zeros((0, 5), dtype=np.float32)

        scores = dets[:, 4]
        boxes = dets[:, :4]
        remain = scores >= self.track_thresh
        dets_h = dets[remain]
        boxes_h = boxes[remain]

        matched, unmatched_trk, unmatched_det = self._associate(dets_h[:, :4], [t["box"] for t in self._tracks])

        for ti, di in matched:
            self._tracks[ti]["box"] = dets_h[di, :4]
            self._tracks[ti]["score"] = float(dets_h[di, 4])
            self._tracks[ti]["last"] = self.frame_id

        for di in unmatched_det:
            self._tracks.append(
                {
                    "id": self._next_id,
                    "box": dets_h[di, :4],
                    "score": float(dets_h[di, 4]),
                    "last": self.frame_id,
                }
            )
            self._next_id += 1

        self._tracks = [t for t in self._tracks if self.frame_id - t["last"] <= self.track_buffer]

        if not self._tracks:
            return np.zeros((0, 5), dtype=np.float32)
        out = np.zeros((len(self._tracks), 5), dtype=np.float32)
        for i, t in enumerate(self._tracks):
            out[i, :4] = t["box"]
            out[i, 4] = t["id"]
        return out

    def _associate(
        self,
        detections: np.ndarray,
        track_boxes: List[np.ndarray],
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not track_boxes:
            return [], [], list(range(len(detections)))
        if len(detections) == 0:
            return [], list(range(len(track_boxes))), []

        tb = np.stack(track_boxes, axis=0)
        ious = _iou_batch(detections, tb)
        matched: List[Tuple[int, int]] = []
        used_t, used_d = set(), set()

        if _HAS_LAP:
            cost = 1.0 - ious
            cost[cost > 1.0 - self.match_thresh] = 1.0
            _, x, y = lap.lapjv(cost, extend_cost=True, limit=1.0 - self.match_thresh)
            for di, ti in enumerate(x):
                if ti >= 0:
                    matched.append((int(ti), int(di)))
                    used_t.add(int(ti))
                    used_d.add(int(di))
        else:
            while True:
                ti, di = np.unravel_index(np.argmax(ious), ious.shape)
                if ious[ti, di] < self.match_thresh:
                    break
                if ti in used_t or di in used_d:
                    ious[ti, di] = -1
                    continue
                matched.append((int(ti), int(di)))
                used_t.add(int(ti))
                used_d.add(int(di))
                ious[ti, :] = -1
                ious[:, di] = -1

        unmatched_trk = [i for i in range(len(track_boxes)) if i not in used_t]
        unmatched_det = [i for i in range(len(detections)) if i not in used_d]
        return matched, unmatched_trk, unmatched_det
