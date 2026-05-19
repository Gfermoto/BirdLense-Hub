#!/usr/bin/env python3
"""Debug canary behavior on a single video id (run inside birdlense container)."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/db/birdlense.db")
    ap.add_argument("--video-id", type=int, required=True)
    ap.add_argument("--config-dir", default="/app/app_config")
    args = ap.parse_args()

    for p in ("/app/processor/src", "/app/scripts", "/app"):
        if p not in sys.path:
            sys.path.insert(0, p)

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    v = con.execute("SELECT * FROM video WHERE id=?", (args.video_id,)).fetchone()
    if not v:
        print(json.dumps({"error": "video not found"}))
        return 1
    rows = con.execute(
        "SELECT id, track_id, frames, detection_provider FROM video_species WHERE video_id=?",
        (args.video_id,),
    ).fetchall()
    con.close()

    dets = []
    species_info = []
    for r in rows:
        fr = json.loads(r["frames"] or "[]")
        dets.append({"frames": fr, "track_id": r["track_id"]})
        species_info.append(
            {"id": r["id"], "track_id": r["track_id"], "n_frames": len(fr), "provider": r["detection_provider"]}
        )

    from app_config.app_config import app_config as cfg

    br = cfg.get("processor.behavior_recognition") or {}

    from behavior_baseline_runtime import maybe_predict_video_behavior_bundle
    from behavior_video_runtime import (
        _load_video_export_labels,
        _resolve_video_openvino_path,
        maybe_predict_video_behavior_video,
    )

    proc = "/app/processor"
    vp = v["video_path"]
    ov = _resolve_video_openvino_path(br, processor_cwd=proc)
    labels = _load_video_export_labels(br, processor_cwd=proc)

    try:
        from shared.behavior_tracklet_crop import runtime_tracklet_rgb_features

        feats = runtime_tracklet_rgb_features(dets, video_path=vp, processor_cwd=proc)
        feat_len = None if feats is None else len(feats)
    except Exception as exc:
        feat_len = f"error:{exc}"

    vl, vc, vk, vv = maybe_predict_video_behavior_video(
        cfg, dets, duration_s=30.0, processor_cwd=proc, video_path=vp
    )
    bundle = maybe_predict_video_behavior_bundle(
        cfg, dets, duration_s=30.0, processor_cwd=proc, video_path=vp
    )

    out = {
        "video_id": args.video_id,
        "video_path": vp,
        "behavior_label": v["behavior_label"],
        "behavior_shadow_label": v["behavior_shadow_label"],
        "species": species_info,
        "engine": br.get("engine"),
        "ov_path": str(ov) if ov else None,
        "labels": labels,
        "feat_len": feat_len,
        "video_pred": {"label": vl, "conf": vc, "kind": vk, "version": vv},
        "bundle": bundle,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
