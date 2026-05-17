#!/usr/bin/env python3
"""Spot-check YOLO on live detect RTSP (704×576 → letterbox 640), not main mp4."""
from __future__ import annotations

import argparse
import sys

import cv2
from ultralytics import YOLO

OV = "/app/processor/models/detection/weights/best_openvino_model"
LORES = (640, 640)
CONF = 0.08


def letterbox_bgr_to_wh(frame, out_wh: tuple[int, int]):
    tw, th = int(out_wh[0]), int(out_wh[1])
    ih, iw = frame.shape[:2]
    r = min(tw / iw, th / ih)
    nw, nh = max(1, int(round(iw * r))), max(1, int(round(ih * r)))
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_x, pad_y = tw - nw, th - nh
    top, bottom = pad_y // 2, pad_y - pad_y // 2
    left, right = pad_x // 2, pad_x - pad_x // 2
    return cv2.copyMakeBorder(
        resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--max-read", type=int, default=90)
    ap.add_argument("--stride", type=int, default=3)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.url)
    if not cap.isOpened():
        print("OPEN_FAIL", args.url, flush=True)
        return 1
    src = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    print(f"src={src[0]}x{src[1]}", flush=True)

    model = YOLO(OV, task="detect")
    frames = hits = 0
    maxc = 0.0
    for i in range(args.max_read):
        ok, fr = cap.read()
        if not ok:
            break
        if i % args.stride:
            continue
        frames += 1
        inp = letterbox_bgr_to_wh(fr, LORES)
        r = model.predict(inp, conf=CONF, verbose=False, imgsz=640, device="intel:gpu")
        n = len(r[0].boxes) if r and r[0].boxes is not None else 0
        if n:
            hits += 1
            maxc = max(maxc, float(r[0].boxes.conf.max()))
    print(f"live_detect_rtsp sampled={frames} hits={hits} max_conf={maxc:.3f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
