#!/usr/bin/env python3
"""Classify bird crops from recordings (Trapper bbox + Birder EU) — for VPS smoke."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
PROC_SRC = REPO / "app" / "processor" / "src"
if str(PROC_SRC) not in sys.path:
    sys.path.insert(0, str(PROC_SRC))

VARIANT = "convnext_v2_tiny_eu-common256px"


def _resolve_video(data_root: Path, raw: str) -> Path | None:
    if not raw:
        return None
    for cand in (Path(raw), data_root / raw, data_root / str(raw).replace("data/", "")):
        if cand.is_file():
            return cand
    return None


def _crops_from_video(video: Path, detector, *, frames: int, conf: float) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        cap.release()
        return []
    step = max(1, total // max(1, frames))
    crops: list[np.ndarray] = []
    for i in range(frames):
        fi = min(total - 1, i * step)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        res = detector(frame, conf=conf, verbose=False)
        if not res or not res[0].boxes or len(res[0].boxes) == 0:
            continue
        xyxy = res[0].boxes.xyxy.cpu().numpy()
        confs = res[0].boxes.conf.cpu().numpy()
        bi = int(confs.argmax())
        x1, y1, x2, y2 = [int(v) for v in xyxy[bi]]
        pad = 8
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        if x2 > x1 and y2 > y1:
            crops.append(frame[y1:y2, x1:x2].copy())
    cap.release()
    return crops


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=Path("/app/data/db/birdlense.db"))
    ap.add_argument("--data-root", type=Path, default=Path("/app/data"))
    ap.add_argument("--weights-root", type=Path, default=Path("/app/processor/models"))
    ap.add_argument("--min-boxes", type=int, default=3, help="Min detector crops per video")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--det-conf", type=float, default=0.25)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--favorite-only", action="store_true")
    ap.add_argument("--video-ids", type=str, default="", help="Comma-separated video ids")
    args = ap.parse_args()

    w = args.weights_root / "classification" / "weights"
    ov = w / f"{VARIANT}_openvino_model"
    det_pt = args.weights_root / "detection" / "weights" / "trapper_ai_v02_2024.pt"
    if not ov.is_dir():
        print(f"MISSING {ov}", file=sys.stderr)
        return 1
    if not det_pt.is_file():
        print(f"MISSING {det_pt}", file=sys.stderr)
        return 1

    from inference.birder_eu_classifier import load_birder_eu_classifier
    from ultralytics import YOLO

    clf = load_birder_eu_classifier(str(ov), backend="openvino", variant=VARIANT, min_confidence=0.1)
    clf.warmup()
    detector = YOLO(str(det_pt))

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    if args.video_ids.strip():
        ids = [int(x) for x in args.video_ids.split(",") if x.strip()]
        rows = conn.execute(
            f"SELECT id, video_path FROM video WHERE id IN ({','.join('?' * len(ids))}) AND deleted_at IS NULL",
            ids,
        ).fetchall()
    elif args.favorite_only:
        rows = conn.execute(
            "SELECT id, video_path FROM video WHERE favorite=1 AND deleted_at IS NULL ORDER BY id DESC",
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT v.id, v.video_path
            FROM video v
            JOIN recording_metrics rm ON rm.video_id = v.id
            WHERE v.deleted_at IS NULL AND rm.yolo_frames_with_tracks >= 30
            ORDER BY rm.yolo_frames_with_tracks DESC
            LIMIT ?
            """,
            (args.limit * 3,),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT id, video_path FROM video WHERE deleted_at IS NULL ORDER BY id DESC LIMIT ?",
                (args.limit * 3,),
            ).fetchall()

    results = []
    for row in rows:
        if len(results) >= args.limit:
            break
        vid = int(row["id"])
        vp = _resolve_video(args.data_root, str(row["video_path"]))
        if vp is None:
            continue
        crops = _crops_from_video(vp, detector, frames=args.frames, conf=args.det_conf)
        if len(crops) < args.min_boxes:
            continue
        tops: dict[str, int] = {}
        jay_rank = None
        for c in crops:
            out = clf.classify_crop_bgr(c)
            label = out.species_name or "?"
            tops[label] = tops.get(label, 0) + 1
            probs = clf._infer_probs(c)
            jay_ids = [i for i, n in clf.names.items() if "eurasian jay" in str(n).lower()]
            if jay_ids:
                best_j = max(jay_ids, key=lambda i: probs[i])
                ranked = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
                if best_j in ranked and jay_rank is None:
                    jay_rank = ranked.index(best_j) + 1
        db_sp = [
            r[0]
            for r in conn.execute(
                """
                SELECT s.name FROM video_species vs
                JOIN species s ON s.id = vs.species_id
                WHERE vs.video_id = ? ORDER BY vs.confidence DESC LIMIT 2
                """,
                (vid,),
            ).fetchall()
        ]
        majority = max(tops, key=tops.get) if tops else None
        results.append(
            {
                "video_id": vid,
                "path": str(row["video_path"]),
                "n_crops": len(crops),
                "db_species": db_sp,
                "birder_majority": majority,
                "birder_votes": tops,
                "jay_best_rank": jay_rank,
            }
        )

    conn.close()
    print(json.dumps({"variant": VARIANT, "n_tested": len(results), "videos": results}, indent=2))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
