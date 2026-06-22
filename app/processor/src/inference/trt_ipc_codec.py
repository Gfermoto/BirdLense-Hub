"""TRT worker IPC codec (py3.6 + py3.11): без pickle numpy 2.x."""

import numpy as np


def encode_frame(frame):
    arr = np.asarray(frame)
    if not arr.flags.c_contiguous:
        arr = np.ascontiguousarray(arr)
    return {
        "shape": list(arr.shape),
        "dtype": arr.dtype.str,
        "data": arr.tobytes(),
    }


def decode_frame(enc):
    if enc is None:
        return None
    if isinstance(enc, np.ndarray):
        return enc
    arr = np.frombuffer(enc["data"], dtype=np.dtype(enc["dtype"]))
    return arr.reshape(tuple(enc["shape"])).copy()


def encode_request(req):
    out = dict(req)
    if "frame" in out:
        out["frame"] = encode_frame(out["frame"])
    return out


def decode_request(req):
    if isinstance(req.get("frame"), dict) and "data" in req["frame"]:
        req = dict(req)
        req["frame"] = decode_frame(req["frame"])
    return req


def encode_boxes_payload(boxes, names=None):
    payload = {
        "xyxy": boxes.xyxy.numpy().tolist(),
        "conf": boxes.conf.numpy().tolist(),
        "cls": boxes.cls.numpy().tolist(),
        "id": boxes.id.numpy().tolist() if boxes.id is not None else None,
        "orig_shape": list(boxes.orig_shape),
    }
    return payload
