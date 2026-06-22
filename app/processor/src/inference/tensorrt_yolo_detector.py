"""Jetson JP4.6: YOLO TensorRT .engine (python3.6 worker)."""

import json
from collections import OrderedDict, namedtuple

import numpy as np

from inference.trt_boxes_shared import TrtBoxes, TrtResult, _PredictorShim
from inference.jetson_trackers.byte_tracker import BYTETracker


class TensorRTYoloDetector:
    names = {0: "Bird"}

    def __init__(self, engine_path, imgsz=704):
        import tensorrt as trt
        import torch

        self._torch = torch
        self.engine_path = str(engine_path)
        self.imgsz = int(imgsz)
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        if self.device.type == "cpu":
            raise RuntimeError(
                "TensorRT YOLO requires CUDA torch on Jetson (use python3.6 + l4t-pytorch stack)",
            )

        Binding = namedtuple("Binding", ("name", "dtype", "shape", "data", "ptr"))
        logger = trt.Logger(trt.Logger.WARNING)
        with open(self.engine_path, "rb") as f, trt.Runtime(logger) as runtime:
            try:
                meta_len = int.from_bytes(f.read(4), byteorder="little")
                metadata = json.loads(f.read(meta_len).decode("utf-8"))
                if isinstance(metadata, dict) and metadata.get("names"):
                    self.names = {int(k): str(v) for k, v in dict(metadata["names"]).items()}
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                f.seek(0)
            engine = runtime.deserialize_cuda_engine(f.read())

        context = engine.create_execution_context()
        bindings = OrderedDict()
        output_names = []
        is_trt10 = not hasattr(engine, "num_bindings")
        num = range(engine.num_io_tensors) if is_trt10 else range(engine.num_bindings)

        for i in num:
            if is_trt10:
                name = engine.get_tensor_name(i)
                dtype = trt.nptype(engine.get_tensor_dtype(name))
                is_input = engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT
                shape = tuple(engine.get_tensor_shape(name))
            else:
                name = engine.get_binding_name(i)
                dtype = trt.nptype(engine.get_binding_dtype(i))
                is_input = engine.binding_is_input(i)
                shape = tuple(engine.get_binding_shape(i))
            if not is_input:
                output_names.append(name)
                continue
            if -1 in shape and not is_trt10:
                context.set_binding_shape(i, (1, 3, self.imgsz, self.imgsz))
                shape = tuple(context.get_binding_shape(i))
            im = torch.from_numpy(np.empty(shape, dtype=dtype)).to(self.device)
            bindings[name] = Binding(name, dtype, shape, im, int(im.data_ptr()))

        for name in output_names:
            if is_trt10:
                oshape = tuple(context.get_tensor_shape(name))
                dtype = trt.nptype(engine.get_tensor_dtype(name))
            else:
                oi = engine.get_binding_index(name)
                oshape = tuple(context.get_binding_shape(oi))
                dtype = trt.nptype(engine.get_binding_dtype(oi))
            out = torch.from_numpy(np.empty(oshape, dtype=dtype)).to(self.device)
            bindings[name] = Binding(name, dtype, oshape, out, int(out.data_ptr()))

        self._engine = engine
        self._context = context
        self._bindings = bindings
        self._output_names = output_names
        self._is_trt10 = is_trt10
        self._binding_addrs = OrderedDict((n, d.ptr) for n, d in bindings.items())
        self._input_name = next(iter(bindings.keys()))
        self.predictor = _PredictorShim(BYTETracker())
        self._tracker_cfg = {}

    def _letterbox(self, frame_bgr):
        h0, w0 = frame_bgr.shape[:2]
        r = min(self.imgsz / h0, self.imgsz / w0)
        nh, nw = int(round(h0 * r)), int(round(w0 * r))
        torch = self._torch
        tensor = torch.from_numpy(frame_bgr).permute(2, 0, 1).unsqueeze(0).float()
        resized_t = torch.nn.functional.interpolate(
            tensor, size=(nh, nw), mode="bilinear", align_corners=False,
        )
        resized = resized_t.squeeze(0).permute(1, 2, 0).byte().cpu().numpy()
        pad_w = (self.imgsz - nw) / 2
        pad_h = (self.imgsz - nh) / 2
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
        top, left = int(round(pad_h - 0.1)), int(round(pad_w - 0.1))
        canvas[top : top + nh, left : left + nw] = resized
        return canvas, r, (pad_w, pad_h)

    def _preprocess(self, frame_bgr):
        im, r, pad = self._letterbox(frame_bgr)
        orig_shape = frame_bgr.shape[:2]
        chw = im[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        batch = np.expand_dims(chw, 0)
        tensor = self._torch.from_numpy(batch).to(self.device)
        return tensor, r, pad, orig_shape

    def _execute(self, tensor):
        torch = self._torch
        in_bind = self._bindings[self._input_name]
        if tuple(tensor.shape) != tuple(in_bind.shape):
            raise ValueError(f"TRT input shape {tensor.shape} != engine {in_bind.shape}")
        self._binding_addrs[self._input_name] = int(tensor.data_ptr())
        if self._is_trt10:
            for name, bind in self._bindings.items():
                if name == self._input_name:
                    self._context.set_tensor_address(name, bind.ptr)
                elif name in self._output_names:
                    self._context.set_tensor_address(name, bind.ptr)
            self._context.execute_async_v3(torch.cuda.current_stream().cuda_stream)
        else:
            self._context.execute_v2(list(self._binding_addrs.values()))
        torch.cuda.synchronize()
        out_name = sorted(self._output_names)[0]
        return self._bindings[out_name].data.detach().cpu().numpy()

    def _postprocess(self, pred, orig_shape, ratio, pad, conf_thres, classes=None):
        """YOLOv8-style [1, 4+nc, N] or [1, N, 4+nc] → xyxy, conf, cls."""
        if pred.ndim == 3:
            p = pred[0]
            if p.shape[0] < p.shape[1] and p.shape[0] <= 64:
                p = p.transpose(1, 0)
        else:
            p = pred
        if p.shape[1] < 6:
            raise ValueError(f"Unexpected TRT output shape {pred.shape}")

        boxes = p[:, :4]
        scores = p[:, 4:]
        if scores.shape[1] == 1:
            cls = np.zeros(len(scores), dtype=np.int64)
            conf = scores[:, 0]
        else:
            cls = np.argmax(scores, axis=1)
            conf = scores[np.arange(len(scores)), cls]

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

        # xywh centre → xyxy in letterbox space
        xyxy = np.zeros_like(boxes)
        xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
        xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
        xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
        xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2

        pad_w, pad_h = pad
        xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - pad_w) / ratio
        xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - pad_h) / ratio
        h, w = orig_shape
        xyxy[:, 0::2] = xyxy[:, 0::2].clip(0, w)
        xyxy[:, 1::2] = xyxy[:, 1::2].clip(0, h)

        # NMS
        idx = self._nms(xyxy, conf, iou_thres=0.45)
        return xyxy[idx], conf[idx], cls[idx].astype(np.int64)

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

    def _predict_raw(self, frame, conf=0.25, classes=None):
        tensor, ratio, pad, orig_shape = self._preprocess(frame)
        raw = self._execute(tensor)
        xyxy, cconf, cls = self._postprocess(
            raw, orig_shape, ratio, pad, float(conf), classes,
        )
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
        if not np.any(valid):
            track_ids_out = None
        else:
            track_ids_out = track_ids

        out = TrtResult(
            TrtBoxes(
                xyxy=xyxy,
                conf=confs,
                cls=clss,
                track_ids=track_ids_out,
                orig_shape=res.boxes.orig_shape,
            )
        )
        return [out]

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


def load_tensorrt_yolo_detector(engine_path):
    import os
    path = engine_path
    if not os.path.isfile(path):
        raise FileNotFoundError("TensorRT engine not found: %s" % engine_path)
    return TensorRTYoloDetector(path, imgsz=704)
