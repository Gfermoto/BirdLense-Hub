#!/usr/bin/env python3
"""YOLO/OpenVINO spot-check: full-res mp4 vs letterbox lores (как live go2rtc)."""
from __future__ import annotations

import argparse
import sys

import cv2
from ultralytics import YOLO

def letterbox_bgr_to_wh(frame, out_wh: tuple[int, int]):
    """Same semantics as processor yolo_geometry (pad 114, keep aspect)."""
    import cv2

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

CLIPS = {
    "105110_yolo_db": "/app/data/recordings/2026/05/17/105110/video.mp4",
    "123830_frigate_only": "/app/data/recordings/2026/05/17/123830/video.mp4",
}
OV = "/app/processor/models/detection/weights/best_openvino_model"
DEVICE = "intel:gpu"
CONF = 0.08
IMGSZ = 640
LORES = (640, 640)
# BirdBox detect RTSP (subtype=1) — как live capture, не main 2688×1520 в video.mp4
DETECT_WH = (704, 576)


def _prep(frame, mode: str):
    if mode == "full":
        return frame
    if mode == "lores":
        # letterbox main → 640 (ближе к processor, но источник всё ещё main-поток)
        return letterbox_bgr_to_wh(frame, LORES)
    if mode == "detect":
        # симуляция: кадр как с detect substream → letterbox inference
        sub = letterbox_bgr_to_wh(frame, DETECT_WH)
        return letterbox_bgr_to_wh(sub, LORES)
    raise ValueError(mode)


def _run_clip(m, path: str, *, mode: str, max_read: int, stride: int) -> tuple[int, int, float, tuple[int, int]]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return 0, 0, 0.0, (0, 0)
    src_wh = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    frames = hits = 0
    maxc = 0.0
    for i in range(max_read):
        ok, fr = cap.read()
        if not ok:
            break
        if i % stride:
            continue
        frames += 1
        inp = _prep(fr, mode)
        r = m.predict(inp, conf=CONF, verbose=False, imgsz=IMGSZ, device=DEVICE)
        n = len(r[0].boxes) if r and r[0].boxes is not None else 0
        if n:
            hits += 1
            maxc = max(maxc, float(r[0].boxes.conf.max()))
    cap.release()
    return frames, hits, maxc, src_wh


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--modes",
        default="full,lores,detect",
        help="full | lores (main→640) | detect (main→704×576→640, как live substream)",
    )
    ap.add_argument("--max-read", type=int, default=150)
    ap.add_argument("--stride", type=int, default=6)
    args = ap.parse_args()
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    model = YOLO(OV, task="detect")
    for tag, path in CLIPS.items():
        for mode in modes:
            frames, hits, maxc, src_wh = _run_clip(
                model,
                path,
                mode=mode,
                max_read=args.max_read,
                stride=args.stride,
            )
            print(
                f"{tag} mode={mode} src={src_wh[0]}x{src_wh[1]} "
                f"infer_px={LORES[0]} "
                f"sampled={frames} hits={hits} max_conf={maxc:.3f}",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
