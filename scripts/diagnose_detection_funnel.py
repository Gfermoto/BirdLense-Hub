#!/usr/bin/env python3
"""
Диагностика воронки live-детекции: raw YOLO → track ids → geometry IoU → accepted.

Запуск на VPS (в контейнере birdlense):
  docker cp scripts/diagnose_detection_funnel.py birdlense:/tmp/
  docker exec birdlense python /tmp/diagnose_detection_funnel.py \\
    --video /app/data/recordings/2026/05/19/151021/video.mp4 \\
    --frames 40 --frame-step 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app"
PROC_SRC = APP / "processor" / "src"
for p in (str(APP), str(PROC_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--frame-step", type=int, default=3)
    parser.add_argument("--write-report", default="")
    args = parser.parse_args()

    if not args.video.is_file():
        print(f"FAIL: video not found: {args.video}", file=sys.stderr)
        return 2

    from app_config.app_config import app_config
    from track_regenerator import build_detection_pipeline
    from frame_geometry import letterbox_roundtrip_iou, prepare_yolo_detector_frame, xyxy_pixels_to_norm
    from pipeline_config import detect_use_native_resolution, resolve_binary_model_imgsz

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        print(f"FAIL: cannot open {args.video}", file=sys.stderr)
        return 2

    fp, _dm = build_detection_pipeline(app_config, for_track_regen=False)
    strategy = fp.strategy
    binary_model = strategy.binary_model
    tracker = str(app_config.get("processor.tracker") or "bytetrack.yaml")
    min_conf = float(app_config.get("processor.min_confidence_binary") or 0.28)
    track_conf = min(
        0.25,
        float(app_config.get("processor.openvino_binary_track_ultralytics_conf") or 0.25),
    )
    imgsz = resolve_binary_model_imgsz(app_config)

    totals = {
        "frames_sampled": 0,
        "raw_boxes": 0,
        "no_track_id_frames": 0,
        "accepted_results": 0,
        "low_roundtrip_iou_boxes": 0,
    }
    per_frame: list[dict] = []

    idx = 0
    sampled = 0
    while sampled < args.frames:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % max(1, args.frame_step) != 0:
            idx += 1
            continue
        idx += 1
        sampled += 1

        det_frame, det_hw, overlay_hw = prepare_yolo_detector_frame(frame, app_config, mode="live")
        oh, ow = int(overlay_hw[0]), int(overlay_hw[1])
        dh, dw = int(det_hw[0]), int(det_hw[1])

        track_out = binary_model.track(
            det_frame,
            persist=True,
            tracker=tracker,
            conf=track_conf,
            imgsz=imgsz,
            verbose=False,
        )
        boxes = track_out[0].boxes if track_out else None
        raw_boxes = len(boxes) if boxes is not None else 0
        no_ids = bool(boxes is not None and len(boxes) > 0 and boxes.id is None)

        rt_ious: list[float] = []
        if boxes is not None and len(boxes) > 0:
            for row in boxes.xyxy.cpu().numpy():
                norm = xyxy_pixels_to_norm(tuple(row), (dh, dw))
                if norm is None:
                    continue
                rt = letterbox_roundtrip_iou(norm, source_shape_hw=(oh, ow), letterbox_shape_hw=(dh, dw))
                rt_ious.append(rt)
                if rt < 0.85:
                    totals["low_roundtrip_iou_boxes"] += 1

        accepted = strategy.detect(det_frame, tracker, min_conf, classification_frame=frame)

        totals["frames_sampled"] += 1
        totals["raw_boxes"] += raw_boxes
        totals["accepted_results"] += len(accepted)
        if no_ids:
            totals["no_track_id_frames"] += 1

        per_frame.append(
            {
                "frame": sampled,
                "overlay_hw": [oh, ow],
                "detector_hw": [dh, dw],
                "native_mode": detect_use_native_resolution(app_config.config),
                "raw_boxes": raw_boxes,
                "no_track_ids": no_ids,
                "accepted": len(accepted),
                "rt_iou_min": round(min(rt_ious), 4) if rt_ious else None,
                "rt_iou_p50": round(float(np.median(rt_ious)), 4) if rt_ious else None,
            }
        )

    cap.release()

    report = {
        "video": str(args.video),
        "config_hints": {
            "detect_use_native_resolution": detect_use_native_resolution(app_config.config),
            "binary_imgsz": app_config.get("processor.binary_imgsz"),
            "inference_lores_wh": app_config.get("processor.inference_lores_wh"),
            "opencv_min_contour_area": app_config.get("triggers.opencv.min_contour_area"),
            "bbox_iou_gate_action": app_config.get("detection.bbox_iou_gate_action"),
        },
        "totals": totals,
        "per_frame": per_frame[:20],
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.write_report:
        Path(args.write_report).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
