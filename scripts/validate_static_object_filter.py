#!/usr/bin/env python3
"""Validate StaticObjectFilter on contrastive roll clips (offline, in birdlense container)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS.parent / "app" / "processor" / "src"))
sys.path.insert(0, str(_SCRIPTS))

from calibrate_nabirds_thresholds import Box, _passes_accept  # noqa: E402
from static_object_filter import StaticObjectFilter, StaticObjectFilterConfig  # noqa: E402


def _parse_boxes(result, frame_idx: int) -> list[Box]:
    out: list[Box] = []
    if not result or not result[0].boxes or len(result[0].boxes) == 0:
        return out
    b = result[0].boxes
    data = b.data.cpu().numpy()
    cls = b.cls.int().cpu().tolist()
    for i in range(len(cls)):
        if int(cls[i]) != 0:
            continue
        x1, y1, x2, y2, c, _ = data[i].tolist()
        out.append(Box((float(x1), float(y1), float(x2), float(y2)), float(c), frame_idx))
    return out


def _to_dict(box: Box, frame_shape: tuple[int, int, int]) -> dict:
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = box.xyxy
    return {
        "track_id": int(box.frame_idx * 1000 + box.cx),
        "detector_label": "Bird",
        "conf": box.conf,
        "crop_coords": (int(x1), int(y1), int(x2), int(y2)),
        "bbox_norm": (x1 / w, y1 / h, x2 / w, y2 / h),
        "box_area_norm": box.area / (w * h),
    }


def analyze_video(
    model,
    video: Path,
    *,
    min_conf: float,
    track_conf: float,
    device: str | None,
    max_frames: int,
    stride: int,
) -> dict:
    filt = StaticObjectFilter(StaticObjectFilterConfig())
    cap = cv2.VideoCapture(str(video))
    fi = 0
    sampled = 0
    before = 0
    after = 0
    bird_before = 0
    bird_after = 0
    rej_static = 0
    rej_phantom = 0
    while cap.isOpened() and sampled < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if fi % stride == 0:
            r = model.predict(
                frame,
                imgsz=640,
                conf=track_conf,
                verbose=False,
                device=device,
                max_det=60,
            )[0]
            raw = _parse_boxes([r], fi)
            acc_dicts = []
            for b in raw:
                ok_b, _ = _passes_accept(
                    b,
                    frame.shape,
                    min_conf=min_conf,
                    min_center_dist=0.01,
                    min_box_px=14,
                    max_area_frac=0.55,
                    max_aspect=4.0,
                    min_aspect=0.15,
                    bg_hist_corr_max=0.92,
                    frame=frame,
                )
                if ok_b:
                    acc_dicts.append(_to_dict(b, frame.shape))
            before += len(acc_dicts)
            for d in acc_dicts:
                ar = (d["crop_coords"][2] - d["crop_coords"][0]) / max(
                    1, d["crop_coords"][3] - d["crop_coords"][1]
                )
                if d["conf"] >= 0.38 or ar <= 0.7 or ar >= 1.4:
                    bird_before += 1
            kept = filt.filter_boxes(acc_dicts, frame_bgr=frame, frame_index=fi)
            after += len(kept)
            rej_static += int(filt.last_stats.get("rejected_static_objects") or 0)
            rej_phantom += int(filt.last_stats.get("rejected_phantom_boxes") or 0)
            for d in kept:
                ar = (d["crop_coords"][2] - d["crop_coords"][0]) / max(
                    1, d["crop_coords"][3] - d["crop_coords"][1]
                )
                if d["conf"] >= 0.38 or ar <= 0.7 or ar >= 1.4:
                    bird_after += 1
            sampled += 1
        fi += 1
    cap.release()
    return {
        "accepted_before": before,
        "accepted_after": after,
        "bird_proxy_before": bird_before,
        "bird_proxy_after": bird_after,
        "rejected_static": rej_static,
        "rejected_phantom": rej_phantom,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=Path("/app/data"))
    ap.add_argument("--model", type=Path, default=Path("/app/processor/models/detection/weights/best_NABirds_openvino_model"))
    ap.add_argument("--device", default="intel:gpu")
    ap.add_argument("--min-conf", type=float, default=0.28)
    ap.add_argument("--track-conf", type=float, default=0.12)
    args = ap.parse_args()

    clips = [
        "recordings/2026/05/20/094147/video.mp4",
        "recordings/2026/05/20/093950/video.mp4",
        "recordings/2026/05/20/050815/video.mp4",
    ]
    from ultralytics import YOLO

    model = YOLO(str(args.model))
    report = {}
    for rel in clips:
        vp = (args.data_root / rel).resolve()
        if not vp.is_file():
            continue
        report[rel] = analyze_video(
            model,
            vp,
            min_conf=args.min_conf,
            track_conf=args.track_conf,
            device=args.device or None,
            max_frames=40,
            stride=2,
        )
    print(json.dumps(report, indent=2))
    ok = True
    if report.get(clips[0], {}).get("accepted_after", 99) >= report.get(clips[0], {}).get("accepted_before", 0):
        ok = False
    if report.get(clips[2], {}).get("bird_proxy_after", 0) < report.get(clips[2], {}).get("bird_proxy_before", 1):
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
