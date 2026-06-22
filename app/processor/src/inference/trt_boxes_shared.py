"""Shared TrtBoxes/TrtResult for TensorRT YOLO (py3.6 + py3.11)."""

import numpy as np


class _TensorLike:
    def __init__(self, data):
        self._data = np.asarray(data)

    def cpu(self):
        return self

    def int(self):
        return _TensorLike(self._data.astype(np.int64))

    def tolist(self):
        return self._data.tolist()

    def numpy(self):
        return self._data


class TrtBoxes:
    def __init__(self, xyxy, conf, cls, track_ids, orig_shape):
        self.xyxy = _TensorLike(xyxy)
        self.conf = _TensorLike(conf)
        self.cls = _TensorLike(cls)
        self.id = _TensorLike(track_ids) if track_ids is not None else None
        self.orig_shape = orig_shape

    @property
    def xyxyn(self):
        h, w = self.orig_shape
        arr = np.asarray(self.xyxy.numpy(), dtype=np.float64).copy()
        if arr.size:
            arr[:, [0, 2]] /= max(float(w), 1.0)
            arr[:, [1, 3]] /= max(float(h), 1.0)
        return _TensorLike(arr)

    def __len__(self):
        return int(len(self.conf.numpy()))


class TrtResult:
    def __init__(self, boxes):
        self.boxes = boxes


class _TrackerReset:
    def __init__(self, tracker):
        self._tracker = tracker

    def reset(self):
        self._tracker.reset()


class _PredictorShim:
    def __init__(self, tracker):
        self.trackers = [_TrackerReset(tracker)]
