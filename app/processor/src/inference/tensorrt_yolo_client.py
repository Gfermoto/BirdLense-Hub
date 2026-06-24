"""TensorRT YOLO client (Python 3.8+): IPC к jetson_trt_worker на python3.6."""

from __future__ import annotations

import logging
import os
import pickle
import socket
import struct
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from inference.trt_boxes_shared import TrtBoxes, TrtResult, _PredictorShim, _TrackerReset
from inference.jetson_trackers.byte_tracker import BYTETracker
from inference.trt_ipc_codec import encode_request


class _TensorLike:
    def __init__(self, data: np.ndarray):
        self._data = np.asarray(data)

    def cpu(self) -> "_TensorLike":
        return self

    def int(self) -> "_TensorLike":
        return _TensorLike(self._data.astype(np.int64))

    def tolist(self) -> list:
        return self._data.tolist()

    def numpy(self) -> np.ndarray:
        return self._data


SOCK = os.environ.get("BIRDLENSE_TRT_SOCKET", "/tmp/birdlense-trt.sock")


def _rpc(req: dict) -> dict:
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.settimeout(120.0)
    conn.connect(SOCK)
    try:
        data = pickle.dumps(encode_request(req), protocol=2)
        conn.sendall(struct.pack("!I", len(data)) + data)
        hdr = conn.recv(4)
        if len(hdr) < 4:
            raise RuntimeError("TRT worker: empty response")
        n = struct.unpack("!I", hdr)[0]
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise RuntimeError("TRT worker: truncated response")
            buf += chunk
        res = pickle.loads(buf)
        if not res.get("ok"):
            raise RuntimeError(res.get("error") or "TRT worker error")
        return res
    finally:
        conn.close()


class TensorRTYoloClient:
    """Ultralytics-like API; inference в python3.6 worker."""

    names: Dict[int, str] = {0: "Bird"}

    def __init__(self, engine_path: str) -> None:
        self.engine_path = engine_path
        import time
        import subprocess

        last_err = None
        max_retries = 300  # ~5 min total
        for attempt in range(max_retries):
            try:
                ping = _rpc({"cmd": "ping"})
                if ping.get("ok"):
                    break
            except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
                last_err = exc
                # Every 30s: check if TRT worker process is alive
                if attempt > 0 and attempt % 30 == 0:
                    try:
                        proc_check = subprocess.run(
                            ["pgrep", "-f", "jetson_trt_worker.py"],
                            capture_output=True, timeout=5,
                        )
                        if proc_check.returncode != 0:
                            logging.getLogger(__name__).warning(
                                "TRT worker not running (attempt %d/%d); waiting...",
                                attempt + 1, max_retries,
                            )
                    except Exception:
                        pass
                time.sleep(1)
        else:
            raise RuntimeError(
                "TRT worker socket not ready after %ds: %s (%s)" % (max_retries, SOCK, last_err)
            )
        tracker = BYTETracker()
        self.predictor = _PredictorShim(tracker)

    def _boxes_from_payload(self, payload: dict) -> TrtResult:
        orig = tuple(payload["orig_shape"])
        tid = payload.get("id")
        return TrtResult(
            TrtBoxes(
                xyxy=np.asarray(payload["xyxy"], dtype=np.float32),
                conf=np.asarray(payload["conf"], dtype=np.float32),
                cls=np.asarray(payload["cls"], dtype=np.int64),
                track_ids=np.asarray(tid, dtype=np.int64) if tid is not None else None,
                orig_shape=orig,
            )
        )

    def predict(self, frame: np.ndarray, **kwargs: Any) -> List[TrtResult]:
        res = _rpc({"cmd": "predict", "frame": frame, "kwargs": kwargs})
        if res.get("names"):
            self.names = {int(k): str(v) for k, v in res["names"].items()}
        return [self._boxes_from_payload(res["boxes"])]

    def track(self, frame: np.ndarray, **kwargs: Any) -> List[TrtResult]:
        if not kwargs.get("persist", True):
            _rpc({"cmd": "reset"})
        res = _rpc({"cmd": "track", "frame": frame, "kwargs": kwargs})
        if res.get("names"):
            self.names = {int(k): str(v) for k, v in res["names"].items()}
        return [self._boxes_from_payload(res["boxes"])]


def load_tensorrt_yolo_client(engine_path: str) -> TensorRTYoloClient:
    return TensorRTYoloClient(engine_path)
