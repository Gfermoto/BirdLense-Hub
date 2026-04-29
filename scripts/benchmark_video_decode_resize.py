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
import subprocess
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True, help="Путь к mp4/mkv и т.п.")
    ap.add_argument("--frames", type=int, default=300, help="Макс. кадров (0 = до EOF)")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=640)
    ap.add_argument("--backend", choices=("opencv", "ffmpeg_vaapi"), default="opencv")
    ap.add_argument("--vaapi-device", default="/dev/dri/renderD128")
    args = ap.parse_args()

    if args.backend == "ffmpeg_vaapi":
        return _run_ffmpeg_vaapi(args)
    try:
        import cv2  # type: ignore
    except ImportError:
        print("Requires opencv-python: pip install opencv-python", file=sys.stderr)
        return 2
    return _run_opencv(args, cv2)


def _run_opencv(args, cv2) -> int:
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
        json_summary("opencv", n, elapsed, fps, ms_per_frame, args.width, args.height),
    )
    return 0


def _ffmpeg_vaapi_cmd(video: str, width: int, height: int, vaapi_device: str) -> list[str]:
    vf = f"scale_vaapi=w={int(width)}:h={int(height)},hwdownload,format=nv12,format=bgr24"
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        vaapi_device,
        "-hwaccel_output_format",
        "vaapi",
        "-i",
        video,
        "-an",
        "-vf",
        vf,
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]


def _run_ffmpeg_vaapi(args) -> int:
    cmd = _ffmpeg_vaapi_cmd(args.video, args.width, args.height, args.vaapi_device)
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, OSError) as e:
        print(f"Cannot start ffmpeg: {e}", file=sys.stderr)
        return 2
    frame_bytes = int(args.width) * int(args.height) * 3
    n = 0
    t0 = time.perf_counter()
    assert proc.stdout is not None
    while True:
        data = proc.stdout.read(frame_bytes)
        if not data:
            break
        if len(data) != frame_bytes:
            break
        n += 1
        if args.frames and n >= args.frames:
            proc.terminate()
            break
    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate(timeout=2)
    elapsed = time.perf_counter() - t0
    if n <= 0 or elapsed <= 0:
        if stderr:
            print(stderr.decode("utf-8", errors="replace")[:1000], file=sys.stderr)
        print("No frames decoded.", file=sys.stderr)
        return 1
    fps = n / elapsed
    ms_per_frame = 1000.0 * elapsed / n
    print(
        json_summary("ffmpeg_vaapi", n, elapsed, fps, ms_per_frame, args.width, args.height),
    )
    return 0


def json_summary(
    backend: str,
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
            "backend": backend,
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
