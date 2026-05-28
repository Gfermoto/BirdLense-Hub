#!/usr/bin/env python3
"""Reclassify video_species via sqlite3 (no Flask) — for locked-DB situations."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

import cv2

os.environ.setdefault("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", "intel:gpu")
sys.path.insert(0, "/app/processor/src")

DB = "/app/data/db/birdlense.db"
DATA = "/app/data"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-ids", required=True)
    ap.add_argument("--min-conf", type=float, default=0.25)
    args = ap.parse_args()
    ids = [int(x) for x in args.video_ids.split(",") if x.strip()]

    from app_config.app_config import app_config
    from inference.birder_eu_classifier import load_birder_eu_classifier
    from species_mapping_config import build_species_mapping
    from species_normalizer import normalize

    clf = load_birder_eu_classifier(
        "/app/processor/models/classification/weights/convnext_v2_tiny_eu-common256px_openvino_model",
        app_config=app_config,
    )
    mapping = build_species_mapping(app_config)

    conn = sqlite3.connect(DB, timeout=120)
    conn.execute("PRAGMA busy_timeout=120000")

    for vid in ids:
        row = conn.execute(
            "SELECT video_path FROM video WHERE id=?", (vid,)
        ).fetchone()
        if not row:
            continue
        rel = row[0]
        path = f"/app/{rel}" if not rel.startswith("/") else rel
        if not os.path.isfile(path):
            path = os.path.join(DATA, rel.replace("data/", "", 1))

        vs_rows = conn.execute(
            "SELECT id, frames FROM video_species WHERE video_id=? AND frames IS NOT NULL",
            (vid,),
        ).fetchall()
        cap = cv2.VideoCapture(path)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        for vs_id, frames_raw in vs_rows:
            try:
                frames = json.loads(frames_raw)
            except json.JSONDecodeError:
                continue
            votes: dict[str, float] = {}
            for fr in frames[:: max(1, len(frames) // 10)]:
                t = float(fr.get("t") or 0)
                bb = fr.get("bbox")
                if not bb:
                    continue
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                ok, frame = cap.read()
                if not ok:
                    continue
                x1, y1, x2, y2 = bb[:4]
                if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
                    x1, y1, x2, y2 = x1 * w, y1 * h, x2 * w, y2 * h
                pad = 8
                crop = frame[
                    max(0, int(y1) - pad) : min(h, int(y2) + pad),
                    max(0, int(x1) - pad) : min(w, int(x2) + pad),
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
                print(f"vid={vid} vs={vs_id}: no votes")
                continue
            best = max(votes.items(), key=lambda kv: kv[1])[0]
            sp = conn.execute("SELECT id FROM species WHERE name=?", (best,)).fetchone()
            if not sp:
                conn.execute("INSERT INTO species (name) VALUES (?)", (best,))
                sp_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            else:
                sp_id = sp[0]
            conf = min(0.99, best and votes[best] / max(1, len(frames)) or 0.5)
            conn.execute(
                "UPDATE video_species SET species_id=?, confidence=? WHERE id=?",
                (sp_id, conf, vs_id),
            )
            print(f"vid={vid} vs={vs_id} -> {best} conf={conf:.3f}")
        cap.release()

    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
