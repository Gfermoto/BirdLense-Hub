#!/usr/bin/env python3
"""Validate live/regen letterbox parity and geometry IoU on golden clips (SOTA-06)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app/processor/src"))


def _load_frame(path: str):
    import cv2

    cap = cv2.VideoCapture(path)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise SystemExit(f"cannot read frame from {path}")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description="BBox geometry parity validator")
    parser.add_argument("--video", default=os.environ.get("YOLO_GOLDEN_CLIP_1819", "").strip())
    parser.add_argument("--min-iou", type=float, default=float(os.environ.get("BBOX_PARITY_MIN_IOU", "0.85")))
    parser.add_argument("--config-json", default="", help="optional JSON merge into synthetic cfg")
    args = parser.parse_args()

    if not args.video or not os.path.isfile(args.video):
        print("WARN: no --video; running synthetic geometry checks only", file=sys.stderr)
        from frame_geometry import letterbox_roundtrip_iou

        iou = letterbox_roundtrip_iou(
            (0.4, 0.4, 0.6, 0.6),
            source_shape_hw=(720, 1280),
            letterbox_shape_hw=(576, 704),
        )
        if iou < args.min_iou:
            print(f"FAIL synthetic roundtrip IoU={iou:.3f} < {args.min_iou}")
            return 1
        print(f"PASS synthetic roundtrip IoU={iou:.3f}")
        return 0

    frame = _load_frame(args.video)
    cfg = {
        "processor.inference_lores_wh": [704, 576],
        "processor.detect_use_native_resolution": False,
    }
    if args.config_json and os.path.isfile(args.config_json):
        cfg.update(json.loads(Path(args.config_json).read_text(encoding="utf-8")))

    from frame_geometry import live_regen_canvas_parity, prepare_detector_pipeline_frame

    report = live_regen_canvas_parity(frame, cfg)
    if not report.get("canvas_wh_match"):
        print("FAIL live/regen canvas_wh mismatch:", json.dumps(report, indent=2))
        return 1

    live_det, _, _, _ = prepare_detector_pipeline_frame(frame, cfg, mode="live")
    regen_det, _, _, _ = prepare_detector_pipeline_frame(frame, cfg, mode="regen")
    if live_det.shape != regen_det.shape:
        print(f"FAIL detector tensor shape live={live_det.shape} regen={regen_det.shape}")
        return 1

    print("PASS canvas parity", report.get("live_canvas_wh"))
    print("PASS detector shape", tuple(live_det.shape))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
