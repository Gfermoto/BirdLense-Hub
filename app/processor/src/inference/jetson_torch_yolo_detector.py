"""TorchScript YOLO detector for Jetson Nano (py3.6 + CUDA torch 1.10)."""

import numpy as np
import torch
from torch.nn import functional as F

from inference.trt_boxes_shared import TrtBoxes, TrtResult, _PredictorShim
from inference.jetson_trackers.byte_tracker import BYTETracker


class JetsonTorchYoloDetector:
    """YOLO detection via TorchScript on Jetson CUDA (no TensorRT)."""

    names = {0: "Bird"}

    def __init__(self, ts_path: str, imgsz: int = 704):
        self.imgsz = imgsz
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        if self.device.type == "cpu":
            raise RuntimeError("Torch YOLO requires CUDA on Jetson")

        self.model = torch.jit.load(ts_path, map_location=self.device)
        self.model.eval()

        try:
            meta = getattr(self.model, "names", None)
            if meta:
                self.names = {int(k): str(v) for k, v in meta.items()}
        except Exception:
            pass

        self.predictor = _PredictorShim(BYTETracker())
        self._tracker_cfg = {}

    # ── preprocessing ────────────────────────────────────────────────

    def _letterbox(self, frame_bgr):
        h0, w0 = frame_bgr.shape[:2]
        r = min(self.imgsz / h0, self.imgsz / w0)
        nh, nw = int(round(h0 * r)), int(round(w0 * r))
        tensor = torch.from_numpy(frame_bgr).permute(2, 0, 1).unsqueeze(0).float()
        resized_t = F.interpolate(tensor, size=(nh, nw), mode="bilinear", align_corners=False)
        resized = resized_t.squeeze(0).permute(1, 2, 0).byte().cpu().numpy()
        pad_w = (self.imgsz - nw) / 2
        pad_h = (self.imgsz - nh) / 2
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
        top, left = int(round(pad_h - 0.1)), int(round(pad_w - 0.1))
        canvas[top: top + nh, left: left + nw] = resized
        return canvas, r, (pad_w, pad_h)

    def _preprocess(self, frame_bgr):
        im, r, pad = self._letterbox(frame_bgr)
        orig_shape = frame_bgr.shape[:2]
        # BGR → RGB, /255, HWC → CHW, add batch
        chw = im[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        tensor = torch.from_numpy(np.expand_dims(chw, 0)).to(self.device)
        return tensor, r, pad, orig_shape

    # ── postprocessing ──────────────────────────────────────────────

    @staticmethod
    def _nms(xyxy, conf, iou_thres=0.45):
        order = conf.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            if order.size == 1:
                break
            rest = order[1:]
            xx1 = np.maximum(xyxy[i, 0], xyxy[rest, 0])
            yy1 = np.maximum(xyxy[i, 1], xyxy[rest, 1])
            xx2 = np.minimum(xyxy[i, 2], xyxy[rest, 2])
            yy2 = np.minimum(xyxy[i, 3], xyxy[rest, 3])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            area_i = (xyxy[i, 2] - xyxy[i, 0]) * (xyxy[i, 3] - xyxy[i, 1])
            area_r = (xyxy[rest, 2] - xyxy[rest, 0]) * (xyxy[rest, 3] - xyxy[rest, 1])
            iou = inter / np.maximum(area_i + area_r - inter, 1e-6)
            order = rest[iou <= iou_thres]
        return np.asarray(keep, dtype=np.int64)

    def _postprocess(self, pred, orig_shape, ratio, pad, conf_thres=0.25, classes=None):
        """Decode YOLOv8 raw output → xyxy, conf, cls."""
        # pred from TorchScript: [1, 22, 10164] → [10164, 22]
        p = pred[0] if pred.ndim == 3 else pred
        if p.shape[0] < p.shape[1]:
            p = p.transpose(1, 0)
        p = p.detach().cpu().numpy()

        boxes = p[:, :4]      # cx, cy, w, h (in letterbox coords)
        scores = p[:, 4:]     # class scores (logits)
        num_classes = scores.shape[1]

        if num_classes == 1:
            cls = np.zeros(len(scores), dtype=np.int64)
            conf = scores[:, 0]
        else:
            cls = np.argmax(scores, axis=1)
            conf = np.max(scores, axis=1)

        keep = conf >= conf_thres
        if classes is not None:
            allow = set(int(c) for c in classes)
            keep &= np.isin(cls, list(allow))
        boxes, conf, cls = boxes[keep], conf[keep], cls[keep]
        if len(boxes) == 0:
            return (
                np.zeros((0, 4), dtype=np.float32),
                np.zeros(0, dtype=np.float32),
                np.zeros(0, dtype=np.int64),
            )

        # cxcywh → xyxy in letterbox space
        xyxy = np.zeros_like(boxes)
        xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
        xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
        xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
        xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2

        # Remove letterbox padding & scale back to original
        pad_w, pad_h = pad
        xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - pad_w) / ratio
        xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - pad_h) / ratio
        h, w = orig_shape
        xyxy[:, 0::2] = xyxy[:, 0::2].clip(0, w)
        xyxy[:, 1::2] = xyxy[:, 1::2].clip(0, h)

        idx = self._nms(xyxy, conf, iou_thres=0.45)
        return xyxy[idx], conf[idx], cls[idx].astype(np.int64)

    # ── inference ───────────────────────────────────────────────────

    def _predict_raw(self, frame, conf=0.25, classes=None):
        tensor, ratio, pad, orig_shape = self._preprocess(frame)
        with torch.no_grad():
            raw = self.model(tensor)
            if isinstance(raw, (list, tuple)):
                raw = raw[0]
        xyxy, cconf, cls = self._postprocess(raw, orig_shape, ratio, pad, float(conf), classes)
        return TrtResult(TrtBoxes(xyxy=xyxy, conf=cconf, cls=cls, track_ids=None, orig_shape=orig_shape))

    def predict(self, frame, **kwargs):
        conf = float(kwargs.get("conf", 0.25))
        classes = kwargs.get("classes")
        return [self._predict_raw(frame, conf=conf, classes=classes)]

    def track(self, frame, **kwargs):
        conf = float(kwargs.get("conf", 0.25))
        classes = kwargs.get("classes")
        persist = bool(kwargs.get("persist", True))
        if not persist:
            self.predictor.trackers[0]._tracker.reset()

        res = self._predict_raw(frame, conf=conf, classes=classes)
        xyxy = res.boxes.xyxy.numpy()
        confs = res.boxes.conf.numpy()
        clss = res.boxes.cls.numpy()
        if len(xyxy) == 0:
            return [TrtResult(TrtBoxes(xyxy=xyxy, conf=confs, cls=clss, track_ids=None, orig_shape=res.boxes.orig_shape))]

        tracker = self.predictor.trackers[0]._tracker
        h, w = res.boxes.orig_shape
        dets = np.concatenate([xyxy, confs.reshape(-1, 1)], axis=1)
        tracks = tracker.update(dets, (h, w), (h, w))
        track_ids = np.full(len(xyxy), -1, dtype=np.int64)
        if tracks is not None and len(tracks):
            tbox = tracks[:, :4]
            tids = tracks[:, 4].astype(np.int64)
            for i, box in enumerate(xyxy):
                if len(tbox) == 0:
                    break
                ious = self._box_iou(box, tbox)
                j = int(np.argmax(ious))
                if ious[j] >= 0.5:
                    track_ids[i] = tids[j]
        valid = track_ids >= 0
        track_ids_out = track_ids if np.any(valid) else None
        return [TrtResult(TrtBoxes(xyxy=xyxy, conf=confs, cls=clss, track_ids=track_ids_out, orig_shape=res.boxes.orig_shape))]

    @staticmethod
    def _box_iou(box, boxes):
        xx1 = np.maximum(box[0], boxes[:, 0])
        yy1 = np.maximum(box[1], boxes[:, 1])
        xx2 = np.minimum(box[2], boxes[:, 2])
        yy2 = np.minimum(box[3], boxes[:, 3])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        area = (box[2] - box[0]) * (box[3] - box[1])
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        return inter / np.maximum(area + areas - inter, 1e-6)


def load_jetson_torch_detector(ts_path: str) -> JetsonTorchYoloDetector:
    if not ts_path.endswith(".torchscript"):
        raise ValueError(f"Expected .torchscript path, got {ts_path!r}")
    return JetsonTorchYoloDetector(ts_path, imgsz=704)
