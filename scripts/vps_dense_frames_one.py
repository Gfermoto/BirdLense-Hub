#!/usr/bin/env python3
"""Dense bbox keyframes via detector + IoU (when ByteTrack/regen misses tail of clip)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

import cv2
import numpy as np
from ultralytics import YOLO

os.environ.setdefault("BIRDLENSE_INFERENCE_DEVICE", "intel:gpu")
DB = os.environ.get("BIRDLENSE_DB", "/app/data/db/birdlense.db")
DET = "/app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model"


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / max(aa + bb - inter, 1e-9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", type=int, required=True)
    ap.add_argument("--frame-step", type=int, default=2)
    ap.add_argument("--conf", type=float, default=0.12)
    ap.add_argument("--imgsz", type=int, default=704)
    args = ap.parse_args()

    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    row = conn.execute("SELECT video_path FROM video WHERE id=?", (args.video_id,)).fetchone()
    if not row:
        return 1
    rel = row[0]
    path = f"/app/{rel}" if not rel.startswith("/") else rel

    cap = cv2.VideoCapture(path)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    det = YOLO(DET)

    frames_out: list[dict] = []
    prev_box: np.ndarray | None = None
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % max(1, args.frame_step) == 0:
            t = idx / fps
            res = det.predict(frame, device="intel:gpu", conf=args.conf, imgsz=args.imgsz, verbose=False)
            if res and res[0].boxes is not None and len(res[0].boxes):
                xyxy = res[0].boxes.xyxy.cpu().numpy()
                confs = res[0].boxes.conf.cpu().numpy()
                bi = int(confs.argmax())
                box = xyxy[bi]
                if prev_box is not None and _iou(prev_box, box) < 0.08:
                    prev_box = box
                else:
                    prev_box = box
                nb = [
                    round(float(box[0] / w), 4),
                    round(float(box[1] / h), 4),
                    round(float(box[2] / w), 4),
                    round(float(box[3] / h), 4),
                ]
                frames_out.append({"t": round(t, 3), "bbox": nb})
        idx += 1
    cap.release()

    if not frames_out:
        print("no detections")
        return 1

    mag = conn.execute("SELECT id FROM species WHERE name='Eurasian Magpie'").fetchone()
    mag_id = mag[0] if mag else None
    if mag_id is None:
        conn.execute("INSERT INTO species (name) VALUES ('Eurasian Magpie')")
        mag_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    t0 = frames_out[0]["t"]
    t1 = frames_out[-1]["t"]
    conn.execute("DELETE FROM video_species WHERE video_id=?", (args.video_id,))
    conn.execute(
        "INSERT INTO video_species (video_id, species_id, start_time, end_time, confidence, source, "
        "detection_provider, track_id, frames) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            args.video_id,
            mag_id,
            t0,
            t1,
            0.8,
            "video",
            "yolo",
            1,
            json.dumps(frames_out),
        ),
    )
    conn.commit()
    print(
        json.dumps(
            {
                "video_id": args.video_id,
                "frames": len(frames_out),
                "t_span": [t0, t1],
                "unique_bbox": len({tuple(f["bbox"]) for f in frames_out}),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
