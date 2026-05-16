#!/usr/bin/env python3
"""Build decode_path_benchmark@v1 by comparing opencv vs ffmpeg_vaapi (#413)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _run_backend(
    *,
    video: str,
    backend: str,
    frames: int,
    width: int,
    height: int,
    vaapi_device: str,
    root_dir: str,
) -> dict[str, Any]:
    cmd = [
        "python3",
        os.path.join(root_dir, "scripts", "benchmark_video_decode_resize.py"),
        "--video",
        video,
        "--backend",
        backend,
        "--frames",
        str(max(1, int(frames))),
        "--width",
        str(max(1, int(width))),
        "--height",
        str(max(1, int(height))),
    ]
    if backend == "ffmpeg_vaapi":
        cmd.extend(["--vaapi-device", vaapi_device])
    proc = subprocess.run(cmd, cwd=root_dir, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {
            "backend": backend,
            "status": "failed",
            "return_code": proc.returncode,
            "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-30:]),
        }
    out = (proc.stdout or "").strip().splitlines()
    if not out:
        return {
            "backend": backend,
            "status": "failed",
            "return_code": 99,
            "stderr_tail": "empty stdout",
        }
    payload = json.loads(out[-1])
    if not isinstance(payload, dict):
        raise ValueError("benchmark output must be JSON object")
    payload["status"] = "ok"
    return payload


def build_decode_path_benchmark_report(
    *,
    opencv_row: dict[str, Any],
    ffmpeg_row: dict[str, Any],
    video: str,
    frames: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    op_ok = str(opencv_row.get("status")) == "ok"
    ff_ok = str(ffmpeg_row.get("status")) == "ok"
    if op_ok:
        op_drop = float(opencv_row.get("drop_rate") or 0.0)
        op_p95 = float(opencv_row.get("p95_frame_delay_ms") or 0.0)
        op_fps = float(opencv_row.get("fps") or 0.0)
    else:
        op_drop = op_p95 = op_fps = 0.0
    if ff_ok:
        ff_drop = float(ffmpeg_row.get("drop_rate") or 0.0)
        ff_p95 = float(ffmpeg_row.get("p95_frame_delay_ms") or 0.0)
        ff_fps = float(ffmpeg_row.get("fps") or 0.0)
    else:
        ff_drop = ff_p95 = ff_fps = 0.0
    drop_improvement = ((op_drop - ff_drop) / op_drop) if (op_ok and ff_ok and op_drop > 0) else None
    p95_improvement = ((op_p95 - ff_p95) / op_p95) if (op_ok and ff_ok and op_p95 > 0) else None
    if not (op_ok and ff_ok):
        drop_gate = False
    elif op_drop > 0:
        drop_gate = bool(drop_improvement is not None and drop_improvement >= 0.20)
    else:
        # Если baseline уже без дропов, считаем gate пройденным при отсутствии регрессии.
        drop_gate = bool(ff_drop <= op_drop)
    gates = {
        "opencv_ok": op_ok,
        "ffmpeg_vaapi_ok": ff_ok,
        "drop_rate_improved_20pct": bool(drop_gate),
    }
    return {
        "schema": "decode_path_benchmark@v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "video": video,
            "frames": int(frames),
            "resize": [int(width), int(height)],
        },
        "results": {
            "opencv": opencv_row,
            "ffmpeg_vaapi": ffmpeg_row,
        },
        "metrics": {
            "opencv_fps": round(op_fps, 3),
            "ffmpeg_vaapi_fps": round(ff_fps, 3),
            "opencv_p95_frame_delay_ms": round(op_p95, 3),
            "ffmpeg_vaapi_p95_frame_delay_ms": round(ff_p95, 3),
            "opencv_drop_rate": round(op_drop, 6),
            "ffmpeg_vaapi_drop_rate": round(ff_drop, 6),
            "drop_rate_improvement_ratio": (None if drop_improvement is None else round(drop_improvement, 6)),
            "p95_frame_delay_improvement_ratio": (None if p95_improvement is None else round(p95_improvement, 6)),
        },
        "gates": gates,
        "ok": all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, help="Benchmark video path.")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--vaapi-device", default="/dev/dri/renderD128")
    parser.add_argument("--out", required=True, help="Path to decode_path_benchmark@v1 JSON.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    opencv_row = _run_backend(
        video=args.video,
        backend="opencv",
        frames=args.frames,
        width=args.width,
        height=args.height,
        vaapi_device=args.vaapi_device,
        root_dir=root_dir,
    )
    ffmpeg_row = _run_backend(
        video=args.video,
        backend="ffmpeg_vaapi",
        frames=args.frames,
        width=args.width,
        height=args.height,
        vaapi_device=args.vaapi_device,
        root_dir=root_dir,
    )
    report = build_decode_path_benchmark_report(
        opencv_row=opencv_row,
        ffmpeg_row=ffmpeg_row,
        video=args.video,
        frames=args.frames,
        width=args.width,
        height=args.height,
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if bool(report.get("ok")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
