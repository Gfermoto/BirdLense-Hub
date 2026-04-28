#!/usr/bin/env python3
"""
Baseline: только декод + resize без YOLO (#373 Phase 1).

Пример::

    python3 scripts/benchmark_video_decode_resize.py --video clip.mp4 --frames 300 \\
      --width 640 --height 640

Нужен OpenCV (как у процессора). Результат — FPS и время на кадр; платформа и env
фиксируйте вручную в таблице (см. docs/CV_ML_DECODE.md).
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    try:
        import cv2  # type: ignore
    except ImportError:
        print("Requires opencv-python: pip install opencv-python", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True, help="Путь к mp4/mkv и т.п.")
    ap.add_argument("--frames", type=int, default=300, help="Макс. кадров (0 = до EOF)")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=640)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Cannot open {args.video}", file=sys.stderr)
        return 2

    n = 0
    t0 = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        cv2.resize(frame, (args.width, args.height), interpolation=cv2.INTER_LINEAR)
        n += 1
        if args.frames and n >= args.frames:
            break
    cap.release()
    elapsed = time.perf_counter() - t0
    if n <= 0 or elapsed <= 0:
        print("No frames decoded.", file=sys.stderr)
        return 1
    fps = n / elapsed
    ms_per_frame = 1000.0 * elapsed / n
    print(
        json_summary(n, elapsed, fps, ms_per_frame, args.width, args.height),
    )
    return 0


def json_summary(
    frames: int,
    elapsed: float,
    fps: float,
    ms_per_frame: float,
    width: int,
    height: int,
) -> str:
    import json

    return json.dumps(
        {
            "schema": "video_decode_resize_benchmark@v1",
            "frames": frames,
            "elapsed_sec": round(elapsed, 4),
            "fps": round(fps, 2),
            "ms_per_frame": round(ms_per_frame, 3),
            "resize": [width, height],
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
