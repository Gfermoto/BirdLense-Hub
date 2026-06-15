#!/usr/bin/env python3
"""Compare YOLO box counts: RTSP subtype=0 vs subtype=1 with production geometry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

_REPO = Path(__file__).resolve().parents[1]
_PROC = _REPO / "app" / "processor" / "src"
if str(_PROC) not in sys.path:
    sys.path.insert(0, str(_PROC))

from frame_geometry import prepare_yolo_detector_frame  # noqa: E402


def _capture_frame(url: str, max_tries: int = 40) -> tuple[object | None, tuple[int, int]]:
    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    frame = None
    wh = (0, 0)
    for _ in range(max_tries):
        ok, fr = cap.read()
        if ok and fr is not None:
            frame = fr
            wh = (int(fr.shape[1]), int(fr.shape[0]))
            break
    cap.release()
    return frame, wh


def _predict_boxes(model, frame, runtime_cfg: dict, conf: float) -> dict:
    det, det_hw, ov_hw = prepare_yolo_detector_frame(frame, runtime_cfg, mode="live")
    imgsz = 704 if det_hw[0] == det_hw[1] else [det_hw[0], det_hw[1]]
    res = model.predict(det, conf=conf, imgsz=imgsz, verbose=False, device="intel:gpu")
    boxes = len(res[0].boxes) if res and res[0].boxes is not None else 0
    max_conf = float(res[0].boxes.conf.max()) if boxes else 0.0
    return {
        "det_hw": list(det_hw),
        "ov_hw": list(ov_hw),
        "imgsz": imgsz,
        "boxes": boxes,
        "max_conf": round(max_conf, 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conf", type=float, default=0.12)
    ap.add_argument("--ov", default="/app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--scan-recordings", type=int, default=0, help="scan N recent mp4 clips")
    ap.add_argument("--frames-per-clip", type=int, default=8)
    args = ap.parse_args()

    urls = {
        "BirdBox_s0": "rtsp://admin:x25xnm00@192.168.1.129:554/cam/realmonitor?channel=1&subtype=0",
        "BirdBox_s1": "rtsp://admin:x25xnm00@192.168.1.129:554/cam/realmonitor?channel=1&subtype=1",
        "Forest_s0": "rtsp://admin:x25xnm00@192.168.1.101:554/cam/realmonitor?channel=1&subtype=0",
        "Forest_s1": "rtsp://admin:x25xnm00@192.168.1.101:554/cam/realmonitor?channel=1&subtype=1",
    }

    runtime_cfg = {
        "processor.inference_lores_wh": [704, 576],
        "processor.inference_backend": "openvino",
        "processor.openvino_native_lores_imgsz": False,
        "processor.binary_imgsz": 704,
        "processor.models.binary_openvino": args.ov,
    }

    from ultralytics import YOLO

    model = YOLO(args.ov)
    report: dict = {"streams": {}, "winner_hint": None}

    for name, url in urls.items():
        frame, wh = _capture_frame(url)
        if frame is None:
            report["streams"][name] = {"error": "no_frame", "capture_wh": list(wh)}
            continue
        pred = _predict_boxes(model, frame, runtime_cfg, args.conf)
        pred["capture_wh"] = list(wh)
        report["streams"][name] = pred

    # Recording fallback: downscale main to lores vs native lores geometry
    rec_root = Path("/app/data/recordings")
    if not rec_root.is_dir():
        rec_root = _REPO / "app" / "data" / "recordings"
    cands = sorted(rec_root.rglob("video.mp4"), reverse=True)
    if cands:
        cap = cv2.VideoCapture(str(cands[0]))
        ok, rec = cap.read()
        cap.release()
        if ok and rec is not None:
            lores = cv2.resize(rec, (704, 576))
            report["recording"] = {
                "path": str(cands[0]),
                "main_wh": [int(rec.shape[1]), int(rec.shape[0])],
                "lores_704x576": _predict_boxes(model, lores, runtime_cfg, args.conf),
            }

    s0_boxes = sum(
        v.get("boxes", 0)
        for k, v in report["streams"].items()
        if k.endswith("_s0") and "error" not in v
    )
    s1_boxes = sum(
        v.get("boxes", 0)
        for k, v in report["streams"].items()
        if k.endswith("_s1") and "error" not in v
    )
    report["totals"] = {"subtype_0_boxes": s0_boxes, "subtype_1_boxes": s1_boxes}
    report["winner_hint"] = "subtype=0" if s0_boxes >= s1_boxes else "subtype=1"

    if args.scan_recordings > 0:
        rec_root = Path("/app/data/recordings")
        if not rec_root.is_dir():
            rec_root = _REPO / "app" / "data" / "recordings"
        cands = sorted(rec_root.rglob("video.mp4"), reverse=True)[: args.scan_recordings]
        scan: list[dict] = []
        tot_s0 = tot_s1 = 0
        for mp4 in cands:
            cap = cv2.VideoCapture(str(mp4))
            s0_hits = s1_hits = sampled = 0
            idx = 0
            main_wh = [0, 0]
            while sampled < args.frames_per_clip:
                ok, fr = cap.read()
                if not ok:
                    break
                if idx % 12:
                    idx += 1
                    continue
                idx += 1
                sampled += 1
                main_wh = [int(fr.shape[1]), int(fr.shape[0])]
                p0 = _predict_boxes(model, fr, runtime_cfg, args.conf)
                lores = cv2.resize(fr, (704, 576)) if main_wh != [704, 576] else fr
                p1 = _predict_boxes(model, lores, runtime_cfg, args.conf)
                s0_hits += 1 if p0["boxes"] else 0
                s1_hits += 1 if p1["boxes"] else 0
            cap.release()
            tot_s0 += s0_hits
            tot_s1 += s1_hits
            if s0_hits or s1_hits:
                scan.append(
                    {
                        "path": str(mp4),
                        "main_wh": main_wh,
                        "s0_hit_frames": s0_hits,
                        "s1_hit_frames": s1_hits,
                        "sampled": sampled,
                    }
                )
        report["recording_scan"] = {
            "clips": len(cands),
            "bird_clips": scan[:10],
            "total_s0_hit_frames": tot_s0,
            "total_s1_hit_frames": tot_s1,
        }
        if tot_s1 > tot_s0:
            report["winner_hint"] = "subtype=1"
        elif tot_s0 > tot_s1:
            report["winner_hint"] = "subtype=0"

    out = json.dumps(report, indent=2)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
