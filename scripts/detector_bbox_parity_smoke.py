#!/usr/bin/env python3
"""Lightweight CI smoke: PT vs OpenVINO bbox IoU gate (#640, Intel iGPU).

Skips (exit 0) when weights or golden clip are absent — no false red on torch-only dev.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PT = REPO / "app/processor/models/detection/weights/best.pt"
DEFAULT_OV = REPO / "app/processor/models/detection/weights/best_openvino_model"
GOLDEN_MANIFEST = REPO / "benchmarks/golden_clips.json"


def _resolve_video(explicit: str) -> Path | None:
    if explicit.strip():
        p = Path(explicit).expanduser()
        return p if p.is_file() else None
    for key in ("DETECTOR_PARITY_VIDEO", "SOTA_GOLDEN_CLIP_1819", "YOLO_GOLDEN_CLIP_1819"):
        raw = os.environ.get(key, "").strip()
        if raw and Path(raw).is_file():
            return Path(raw)
    if GOLDEN_MANIFEST.is_file():
        try:
            data = json.loads(GOLDEN_MANIFEST.read_text(encoding="utf-8"))
            clip = (data.get("clips") or {}).get("1819") or {}
            fixture = clip.get("fixture_path") or ""
            if fixture:
                candidate = REPO / fixture
                if candidate.is_file():
                    return candidate
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return None


def _resolve_weights(pt: str, ov: str) -> tuple[Path | None, Path | None]:
    pt_path = Path(pt).expanduser() if pt else DEFAULT_PT
    ov_path = Path(ov).expanduser() if ov else DEFAULT_OV
    pt_ok = pt_path.is_file()
    ov_ok = ov_path.is_dir() and any(ov_path.glob("*.xml"))
    return (pt_path if pt_ok else None, ov_path if ov_ok else None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", default="", help="mp4 path (env DETECTOR_PARITY_VIDEO fallback)")
    parser.add_argument("--model-a", default="", help="PyTorch .pt (default: best.pt)")
    parser.add_argument("--model-b", default="", help="OpenVINO IR dir (default: best_openvino_model)")
    parser.add_argument("--min-median-iou", type=float, default=0.45)
    parser.add_argument("--clip-id", default="1819")
    parser.add_argument("--device", default=os.environ.get("BIRDLENSE_INFERENCE_DEVICE", "intel:gpu"))
    parser.add_argument("--frame-step", type=int, default=4)
    parser.add_argument("--conf", type=float, default=0.2)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--dry-run", action="store_true", help="Print skip/run decision only")
    args = parser.parse_args()

    if os.environ.get("SKIP_DETECTOR_BBOX_PARITY", "").strip() in {"1", "true", "yes"}:
        print(json.dumps({"status": "skipped", "reason": "SKIP_DETECTOR_BBOX_PARITY"}))
        return 0

    video = _resolve_video(args.video)
    pt, ov = _resolve_weights(args.model_a, args.model_b)
    missing: list[str] = []
    if video is None:
        missing.append("video")
    if pt is None:
        missing.append("model_a_pt")
    if ov is None:
        missing.append("model_b_openvino")

    if missing:
        report = {
            "status": "skipped",
            "reason": "missing_prerequisites",
            "missing": missing,
            "hint": "set DETECTOR_PARITY_VIDEO or fetch weights; see docs/contributor/detector-bbox-parity.md",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    cmd = [
        sys.executable,
        str(REPO / "scripts/compare_detector_bboxes.py"),
        "--video",
        str(video),
        "--model-a",
        str(pt),
        "--model-b",
        str(ov),
        "--bird-class-ids-a",
        "0",
        "--bird-class-ids-b",
        "0",
        "--imgsz",
        str(args.imgsz),
        "--conf",
        str(args.conf),
        "--frame-step",
        str(args.frame_step),
        "--device",
        args.device,
        "--min-median-iou",
        str(args.min_median_iou),
        "--clip-id",
        args.clip_id,
    ]
    if args.dry_run:
        print(json.dumps({"status": "would_run", "cmd": cmd}))
        return 0

    proc = subprocess.run(cmd, cwd=str(REPO), check=False)
    return int(proc.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
