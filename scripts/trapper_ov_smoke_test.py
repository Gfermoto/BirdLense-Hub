#!/usr/bin/env python3
"""Smoke: load Trapper OpenVINO @704 and run predict on dummy + optional video frame."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ov-dir", default="app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model")
    ap.add_argument("--imgsz", type=int, default=704)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="")
    ap.add_argument("--video", default="")
    ap.add_argument("--frame-index", type=int, default=0)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    ov = Path(args.ov_dir)
    if not ov.is_absolute():
        ov = (repo / ov).resolve()
    meta = ov / "metadata.yaml"
    if not meta.is_file():
        print(json.dumps({"ok": False, "error": "missing_metadata", "path": str(meta)}))
        return 1
    text = meta.read_text(encoding="utf-8")
    if "704" not in text:
        print(json.dumps({"ok": False, "error": "metadata_not_704", "path": str(meta)}))
        return 1

    import numpy as np
    from ultralytics import YOLO

    m = YOLO(str(ov))
    kw: dict = {"verbose": False, "imgsz": int(args.imgsz), "conf": float(args.conf)}
    if args.device.strip():
        kw["device"] = args.device.strip()

    if args.video.strip():
        import cv2

        src = Path(args.video)
        if not src.is_absolute():
            src = (repo / src).resolve()
        cap = cv2.VideoCapture(str(src))
        if args.frame_index > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(args.frame_index))
        ok, bgr = cap.read()
        cap.release()
        if not ok or bgr is None:
            print(json.dumps({"ok": False, "error": "frame_read_failed", "video": str(src)}))
            return 1
        frame = np.asarray(bgr, dtype=np.uint8)
    else:
        frame = np.zeros((576, 704, 3), dtype=np.uint8)

    pred = m.predict(frame, **kw)
    n = int(len(pred[0].boxes)) if pred and pred[0].boxes is not None else 0
    names = []
    if n:
        for i in range(min(n, 8)):
            cid = int(pred[0].boxes.cls[i].item())
            conf = float(pred[0].boxes.conf[i].item())
            names.append({"class_id": cid, "name": str(m.names.get(cid, cid)), "conf": round(conf, 4)})

    out = {
        "ok": True,
        "ov_dir": str(ov),
        "imgsz": args.imgsz,
        "frame_shape": list(frame.shape),
        "detections": n,
        "sample": names,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
