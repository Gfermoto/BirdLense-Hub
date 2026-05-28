#!/usr/bin/env python3
"""One-video track regen + DB persist (container)."""
from __future__ import annotations

import argparse
import json
import os
import sys

os.environ.setdefault("BIRDLENSE_INFERENCE_BACKEND", "openvino")
os.environ.setdefault("BIRDLENSE_INFERENCE_DEVICE", "intel:gpu")
os.environ.setdefault("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", "openvino")
os.environ.setdefault("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", "intel:gpu")

sys.path[:0] = ["/app", "/app/web", "/app/processor/src"]
os.chdir("/app/web")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", type=int, required=True)
    ap.add_argument("--frame-step", type=int, default=5)
    args = ap.parse_args()

    from app import create_app
    from app_config.app_config import app_config

    app_config.set("processor.track_regen_match_live_pipeline", True)
    app_config.set("processor.track_regen_frame_step", args.frame_step)
    app_config.set("processor.track_regen_video_timeout_sec", 900)
    app_config.set("processor.track_regen_precise_timeout_sec", 900)
    # Regen smoke: мягче детектор/трек, чтобы frames покрывали весь визит.
    app_config.set("processor.min_confidence_binary_bird", 0.14)
    app_config.set("processor.openvino_binary_track_ultralytics_conf", 0.14)
    app_config.set("processor.birder_eu_min_confidence", 0.18)

    from app import create_app as _ca  # noqa: F811

    app = _ca()
    with app.app_context():
        from data_paths import resolve_recording_video_file
        from detection_fusion import build_fused_video_detections
        from inference_lores import resolve_track_regen_lores_size
        from models import Video, VideoSpecies, db
        from services.visit_processor import VisitProcessor
        from track_regenerator import build_detection_pipeline, process_video_for_tracks

        v = db.session.get(Video, args.video_id)
        if not v:
            print(json.dumps({"error": "not_found"}))
            return 1
        path = resolve_recording_video_file(v.video_path)
        lores = resolve_track_regen_lores_size(app_config)
        fp, dm = build_detection_pipeline(app_config, for_track_regen=True)
        raw = process_video_for_tracks(
            path,
            lores_size=lores,
            frame_processor=fp,
            decision_maker=dm,
            frame_step=args.frame_step,
            max_runtime_sec=1200,
        )
        fused = build_fused_video_detections(
            raw,
            [],
            start_time=v.start_time,
            end_time=v.end_time,
            app_config=app_config,
        )
        VideoSpecies.query.filter_by(video_id=v.id).delete()
        vp = VisitProcessor(db, app.logger, visit_timeout=60, update_species_metadata=False)
        vp.process_detections(v, fused)
        db.session.commit()
        out = {
            "video_id": v.id,
            "lores": list(lores),
            "frame_step": args.frame_step,
            "raw": len(raw),
            "fused": [
                {
                    "species": d.get("species_name"),
                    "conf": d.get("confidence"),
                    "track_id": d.get("track_id"),
                    "frames": len(d.get("frames") or []),
                }
                for d in fused
            ],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
