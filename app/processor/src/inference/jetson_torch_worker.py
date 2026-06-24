#!/usr/bin/env python3.6
"""Jetson Nano: TorchScript YOLO worker (py3.6 + CUDA torch 1.10). Unix socket server."""

from __future__ import print_function

import os
import pickle
import socket
import struct
import sys
import traceback

from inference.trt_ipc_codec import decode_request, encode_boxes_payload, encode_request

ROOT = os.environ.get("BIRDLENSE_TRT_WORKER_ROOT", "/app/processor/src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SOCK = os.environ.get("BIRDLENSE_TRT_SOCKET", "/tmp/birdlense-trt.sock")


def _send(conn, obj):
    data = pickle.dumps(obj, protocol=2)
    conn.sendall(struct.pack("!I", len(data)) + data)


def _recv(conn):
    hdr = conn.recv(4)
    if len(hdr) < 4:
        return None
    n = struct.unpack("!I", hdr)[0]
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return pickle.loads(buf)


def main():
    # Determine TorchScript path
    ts_path = os.environ.get("BIRDLENSE_BINARY_TORCHSCRIPT_PATH", "")
    if not ts_path:
        # fallback: derive from TENSORRT path (same dir, .torchscript)
        trt_path = os.environ.get("BIRDLENSE_BINARY_TENSORRT_PATH", "")
        if trt_path:
            base = os.path.splitext(trt_path)[0]
            ts_path = base + ".torchscript"
        else:
            ts_path = "models/detection/trapper_ai_v02_2024/weights/trapper_ai_v02_2024.torchscript"
    if not ts_path.startswith("/"):
        ts_path = os.path.join("/app/processor", ts_path)

    from inference.jetson_torch_yolo_detector import JetsonTorchYoloDetector

    model = JetsonTorchYoloDetector(ts_path, imgsz=704)
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    os.chmod(SOCK, 0o666)
    srv.listen(4)
    sys.stderr.write("jetson_torch_worker: listening %s ts=%s names=%s\n" % (SOCK, ts_path, model.names))
    sys.stderr.flush()

    while True:
        conn, _ = srv.accept()
        try:
            while True:
                req = _recv(conn)
                if req is None:
                    break
                req = decode_request(req)
                cmd = req.get("cmd")
                if cmd == "ping":
                    _send(conn, {"ok": True, "cuda": True})
                    continue
                if cmd == "track":
                    frame = req["frame"]
                    kwargs = req.get("kwargs") or {}
                    out = model.track(frame, **kwargs)
                    boxes = out[0].boxes
                    payload = encode_boxes_payload(boxes, model.names)
                    _send(conn, {"ok": True, "boxes": payload, "names": model.names})
                    continue
                if cmd == "predict":
                    frame = req["frame"]
                    out = model.predict(frame, **(req.get("kwargs") or {}))
                    boxes = out[0].boxes
                    payload = encode_boxes_payload(boxes, model.names)
                    _send(conn, {"ok": True, "boxes": payload, "names": model.names})
                    continue
                if cmd == "reset":
                    model.predictor.trackers[0]._tracker.reset()
                    _send(conn, {"ok": True})
                    continue
                _send(conn, {"ok": False, "error": "unknown cmd"})
        except Exception as exc:
            _send(conn, {"ok": False, "error": str(exc), "trace": traceback.format_exc()})
        finally:
            conn.close()


if __name__ == "__main__":
    main()
