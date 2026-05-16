#!/usr/bin/env python3
"""Extract one normalized-bbox crop from a video file (AL / tooling).

Uses OpenCV read + resize crop to JPEG. Coordinates are xyxy normalized 0..1.

Example::

  python3 scripts/active_learning/export_crop_from_video.py \\
    --video clip.mp4 --time-sec 1.5 --bbox 0.1,0.2,0.6,0.9 --out crop.jpg
"""

from __future__ import annotations

import argparse
import math
import os
import sys

import cv2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True)
    ap.add_argument("--time-sec", type=float, required=True)
    ap.add_argument("--bbox", required=True, help="x1,y1,x2,y2 normalized 0..1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    parts = [float(x.strip()) for x in args.bbox.split(",")]
    if len(parts) != 4:
        print("bbox must have 4 comma-separated floats", file=sys.stderr)
        return 2
    x1n, y1n, x2n, y2n = parts

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"cannot_open:{args.video}", file=sys.stderr)
        return 2
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if fps <= 0:
            fps = 30.0
        frame_idx = max(0, int(round(float(args.time_sec) * fps)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok or frame is None:
            print("read_failed_at_frame", frame_idx, file=sys.stderr)
            return 2
        h, w = frame.shape[:2]
        x1 = max(0, min(w - 1, int(math.floor(x1n * w))))
        y1 = max(0, min(h - 1, int(math.floor(y1n * h))))
        x2 = max(0, min(w, int(math.ceil(x2n * w))))
        y2 = max(0, min(h, int(math.ceil(y2n * h))))
        if x2 <= x1 or y2 <= y1:
            print("bad_bbox_after_px", x1, y1, x2, y2, file=sys.stderr)
            return 2
        crop = frame[y1:y2, x1:x2]
        parent = os.path.dirname(os.path.abspath(args.out))
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not cv2.imwrite(args.out, crop):
            print("imwrite_failed", args.out, file=sys.stderr)
            return 2
    finally:
        cap.release()
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
