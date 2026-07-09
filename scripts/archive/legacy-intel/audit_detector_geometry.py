#!/usr/bin/env python3
"""
Pipeline-aware PT vs OpenVINO bbox audit on MP4 (simulates live detect substream geometry).

Unlike compare_detector_bboxes.py (raw frame → YOLO), this script:
1. Downscales main record to inference_lores_wh (704×576)
2. Letterboxes to OpenVINO square IR canvas (704×704) when backend=openvino
3. Runs both models with production imgsz resolution

Usage (in birdlense container):
  python3 /app/scripts/audit_detector_geometry.py \\
    --video /app/data/recordings/2026/06/14/064927/video.mp4 \\
    --pt models/detection/weights/trapper_ai_v02_2024.pt \\
    --ov models/detection/weights/trapper_ai_v02_2024_openvino_model \\
    --conf 0.12 --frame-step 15
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

_REPO = Path(__file__).resolve().parents[1]
_PROC = _REPO / "app" / "processor" / "src"
if str(_PROC) not in sys.path:
    sys.path.insert(0, str(_PROC))

from frame_geometry import (  # noqa: E402
    DetectorGeometry,
    bbox_norm_detector_to_overlay,
    prepare_yolo_detector_frame,
    unmap_letterbox_norm_xyxy_to_source_norm_xyxy,
)
from pipeline_config import resolve_detector_letterbox_wh  # noqa: E402


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    ua = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    ub = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = ua + ub - inter
    return float(inter / union) if union > 0 else 0.0


def _bird_boxes_overlay(model, det_bgr, imgsz, conf, bird_ids: set[int], geometry: DetectorGeometry):
    from ultralytics import YOLO

    if not isinstance(model, YOLO):
        model = YOLO(model)
    res = model.predict(det_bgr, imgsz=imgsz, conf=conf, verbose=False)
    if not res or not res[0].boxes:
        return []
    b = res[0].boxes
    out = []
    xyxyn = b.xyxyn.cpu().numpy()
    cls = b.cls.int().cpu().tolist()
    for i, c in enumerate(cls):
        if int(c) not in bird_ids:
            continue
        norm = tuple(float(x) for x in xyxyn[i])
        ov = bbox_norm_detector_to_overlay(norm, geometry=geometry)
        if ov is None:
            continue
        out.append(ov)
    return out


def _lores_from_main(frame: np.ndarray, lores_wh: tuple[int, int]) -> np.ndarray:
    tw, th = lores_wh
    h, w = frame.shape[:2]
    if w == tw and h == th:
        return frame
    return cv2.resize(frame, (tw, th), interpolation=cv2.INTER_LINEAR)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", required=True)
    p.add_argument("--pt", required=True)
    p.add_argument("--ov", required=True)
    p.add_argument("--conf", type=float, default=0.12)
    p.add_argument("--frame-step", type=int, default=10)
    p.add_argument("--lores-wh", default="704,576")
    p.add_argument("--bird-class-id", type=int, default=0)
    args = p.parse_args()

    lw = tuple(int(x) for x in args.lores_wh.split(","))
    runtime_cfg = {
        "processor.inference_lores_wh": list(lw),
        "processor.detect_use_native_resolution": False,
        "processor.inference_backend": "openvino",
        "processor.models.binary_openvino": args.ov,
        "processor.binary_imgsz": 704,
        "processor.openvino_native_lores_imgsz": True,
    }
    canvas = resolve_detector_letterbox_wh(runtime_cfg, (lw[1], lw[0]))
    assert canvas is not None

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(json.dumps({"error": f"cannot open {args.video}"}))
        return 2

    from ultralytics import YOLO

    pt_model = YOLO(args.pt)
    ov_model = YOLO(args.ov)
    bird_ids = {args.bird_class_id}
    ious: list[float] = []
    frames_a = frames_b = frames_both = sampled = 0
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % args.frame_step != 0:
            idx += 1
            continue
        idx += 1
        sampled += 1
        lores = _lores_from_main(frame, lw)
        det, det_hw, ov_hw = prepare_yolo_detector_frame(lores, runtime_cfg, mode="live")
        geometry = DetectorGeometry(detector_shape_hw=det_hw, overlay_shape_hw=ov_hw)
        imgsz = 704 if det_hw[0] == det_hw[1] else [det_hw[0], det_hw[1]]
        boxes_a = _bird_boxes_overlay(pt_model, det, imgsz, args.conf, bird_ids, geometry)
        boxes_b = _bird_boxes_overlay(ov_model, det, imgsz, args.conf, bird_ids, geometry)
        if boxes_a:
            frames_a += 1
        if boxes_b:
            frames_b += 1
        if boxes_a and boxes_b:
            frames_both += 1
            best = 0.0
            for ba in boxes_a:
                for bb in boxes_b:
                    best = max(best, _iou(ba, bb))
            ious.append(best)

    cap.release()
    report = {
        "video": args.video,
        "lores_wh": list(lw),
        "canvas_wh": list(canvas),
        "conf": args.conf,
        "sampled_frames": sampled,
        "frames_with_bird_pt": frames_a,
        "frames_with_bird_ov": frames_b,
        "frames_with_both": frames_both,
        "mean_iou_overlay_norm": float(sum(ious) / len(ious)) if ious else None,
        "median_iou_overlay_norm": float(sorted(ious)[len(ious) // 2]) if ious else None,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
