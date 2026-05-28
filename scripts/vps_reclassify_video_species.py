#!/usr/bin/env python3
"""Re-classify video_species rows from stored frame bboxes (Birder EU, GPU)."""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

os.environ.setdefault("BIRDLENSE_INFERENCE_BACKEND", "openvino")
os.environ.setdefault("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", "openvino")
os.environ.setdefault("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", "intel:gpu")

sys.path[:0] = ["/app", "/app/web", "/app/processor/src"]
os.chdir("/app/web")


def _bbox_px(bbox: list, w: int, h: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox[:4]
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        return int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
    return int(x1), int(y1), int(x2), int(y2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-ids", required=True)
    ap.add_argument("--min-conf", type=float, default=0.35)
    args = ap.parse_args()
    ids = [int(x) for x in args.video_ids.split(",") if x.strip()]

    from app import create_app
    from app_config.app_config import app_config
    from data_paths import resolve_recording_video_file
    from inference.birder_eu_classifier import load_birder_eu_classifier
    from models import Species, Video, VideoSpecies, db
    from species_normalizer import normalize
    from species_mapping_config import build_species_mapping

    clf = load_birder_eu_classifier(
        "/app/processor/models/classification/weights/convnext_v2_tiny_eu-common256px_openvino_model",
        app_config=app_config,
    )
    mapping = build_species_mapping(app_config)

    app = create_app()
    with app.app_context():
        for vid in ids:
            video = db.session.get(Video, vid)
            if not video:
                print(f"skip {vid}: not found")
                continue
            path = resolve_recording_video_file(video.video_path)
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                print(f"skip {vid}: cannot open {path}")
                continue
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)

            for vs in list(video.video_species):
                if vs.manually_corrected:
                    continue
                try:
                    frames = json.loads(vs.frames or "[]")
                except json.JSONDecodeError:
                    frames = []
                if not frames:
                    continue
                votes: dict[str, float] = {}
                for fr in frames[:: max(1, len(frames) // 8)]:
                    t = float(fr.get("t") or 0)
                    bb = fr.get("bbox")
                    if not bb:
                        continue
                    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue
                    x1, y1, x2, y2 = _bbox_px(list(bb), w, h)
                    pad = 8
                    crop = frame[
                        max(0, y1 - pad) : min(h, y2 + pad),
                        max(0, x1 - pad) : min(w, x2 + pad),
                    ]
                    if crop.size == 0:
                        continue
                    r = clf.classify_crop_bgr(crop)
                    name = normalize(r.species_name or "", mapping) if r.species_name else ""
                    if not name or name.lower() in {"unknown", "unknown bird", "bird"}:
                        continue
                    if r.top1_confidence < args.min_conf:
                        continue
                    votes[name] = votes.get(name, 0.0) + r.top1_confidence
                if not votes:
                    print(f"  vs#{vs.id} vid={vid}: no votes")
                    continue
                best = max(votes.items(), key=lambda kv: kv[1])
                sp = db.session.query(Species).filter(Species.name == best[0]).first()
                if not sp:
                    sp = Species(name=best[0])
                    db.session.add(sp)
                    db.session.flush()
                old = vs.species.name if vs.species else "?"
                vs.species_id = sp.id
                vs.confidence = min(0.99, best[1] / max(1, len(frames)))
                print(f"  vid={vid} vs#{vs.id}: {old} -> {best[0]} (score={best[1]:.2f})")
            cap.release()
        db.session.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
