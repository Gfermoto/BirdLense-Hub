#!/usr/bin/env python3
"""A/B birder_eu vs efficientnet_b2 on favorite recordings (detector crops)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
PROC_SRC = REPO / "app" / "processor" / "src"
if str(PROC_SRC) not in sys.path:
    sys.path.insert(0, str(PROC_SRC))

WEIGHTS = REPO / "app" / "processor" / "models" / "classification" / "weights"
DET_PT = REPO / "app" / "processor" / "models" / "detection" / "weights" / "best.pt"


@dataclass
class VideoAbRow:
    video_id: int
    video_path: str
    db_top_species: list[str]
    n_crops: int
    birder_top1: str | None
    birder_raw_top1: str | None
    birder_conf: float
    birder_ms_per_crop: float
    efficientnet_top1: str | None
    efficientnet_conf: float
    efficientnet_ms_per_crop: float
    agree_with_db: bool
    agree_raw_with_db: bool
    engines_agree: bool
    birder_jay_rank: int | None
    efficientnet_jay_rank: int | None
    efficientnet_absurd: bool


def _resolve_video_path(data_root: Path, raw: str) -> Path | None:
    if not raw:
        return None
    p = Path(raw)
    if p.is_file():
        return p
    for cand in (
        data_root / raw,
        data_root / "recordings" / raw.replace("data/recordings/", "").lstrip("/"),
        data_root / raw.lstrip("data/"),
    ):
        if cand.is_file():
            return cand
    return None


def _db_labels(conn: sqlite3.Connection, video_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT s.name, vs.confidence
        FROM video_species vs
        JOIN species s ON s.id = vs.species_id
        WHERE vs.video_id = ?
        ORDER BY vs.confidence DESC
        LIMIT 3
        """,
        (video_id,),
    ).fetchall()
    return [str(r[0]) for r in rows]


def _normalize_name(name: str | None) -> str:
    return " ".join(str(name or "").lower().split())


def _names_match(a: str, b: str) -> bool:
    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def _extract_crops(
    video: Path,
    detector,
    *,
    sample_frames: int,
    min_conf: float,
) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        cap.release()
        return []
    if sample_frames <= 1:
        indices = [total // 2]
    else:
        step = max(1, total // sample_frames)
        indices = [min(total - 1, i * step) for i in range(sample_frames)]

    crops: list[np.ndarray] = []
    for fi in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        results = detector(frame, conf=min_conf, verbose=False)
        if not results:
            continue
        r0 = results[0]
        boxes = getattr(r0, "boxes", None)
        if boxes is None or len(boxes) == 0:
            h, w = frame.shape[:2]
            crops.append(frame[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4])
            continue
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        best_i = int(confs.argmax())
        x1, y1, x2, y2 = [int(v) for v in xyxy[best_i]]
        pad = 8
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        if x2 > x1 and y2 > y1:
            crops.append(frame[y1:y2, x1:x2].copy())
    cap.release()
    return crops


def _birder_raw_top1(clf, crop: np.ndarray) -> tuple[str, float]:
    probs = clf._infer_probs(crop)
    best_id = int(np.argmax(probs))
    conf = float(probs[best_id])
    label = clf.id2label.get(best_id, clf.unknown_label)
    return str(label), conf


def _majority_vote(
    clf,
    crops: list[np.ndarray],
    *,
    raw_votes: bool = False,
) -> tuple[str | None, str | None, float, float, int | None]:
    if not crops:
        return None, None, 0.0, 0.0, None
    t0 = time.perf_counter()
    votes: Counter[str] = Counter()
    raw_vote: Counter[str] = Counter()
    conf_sum: dict[str, float] = {}
    jay_ranks: list[int] = []
    names = getattr(clf, "names", None) or getattr(clf, "id2label", {}) or {}
    is_birder = hasattr(clf, "_infer_probs")
    for crop in crops:
        out = clf.classify_crop_bgr(crop)
        label = out.species_name or "Unknown"
        votes[label] += 1
        conf_sum[label] = conf_sum.get(label, 0.0) + float(out.top1_confidence)
        if raw_votes and is_birder:
            raw_label, _ = _birder_raw_top1(clf, crop)
            raw_vote[raw_label] += 1
        jay_ids = [i for i, n in names.items() if "eurasian jay" in str(n).lower()]
        if is_birder:
            probs = clf._infer_probs(crop)
            if jay_ids:
                best_j = max(jay_ids, key=lambda i: probs[i] if i < len(probs) else 0.0)
                ranked = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
                if best_j in ranked:
                    jay_ranks.append(ranked.index(best_j) + 1)
        elif "jay" in label.lower():
            jay_ranks.append(1)
    ms = (time.perf_counter() - t0) * 1000.0 / len(crops)
    top1 = votes.most_common(1)[0][0]
    raw_top1 = raw_vote.most_common(1)[0][0] if raw_vote else top1
    avg_conf = conf_sum[top1] / max(1, votes[top1])
    jay_rank = min(jay_ranks) if jay_ranks else None
    return top1, raw_top1, avg_conf, ms, jay_rank


_ABSURD_EFFICIENTNET = frozenset(
    {
        "demoiselle crane",
        "peacock",
        "dalmatian pelican",
        "red billed tropicbird",
        "snowy owl",
        "jacobin pigeon",
        "willow ptarmigan",
        "grey cuckooshrike",
        "go away bird",
        "laughing gull",
    }
)


def _load_classifiers(backend: str):
    from inference.birder_eu_classifier import load_birder_eu_classifier

    variant = "convnext_v2_tiny_eu-common256px"
    birder_dir = WEIGHTS / f"{variant}_openvino_model"
    birder = load_birder_eu_classifier(
        str(birder_dir),
        backend=backend,
        variant=variant,
        min_confidence=0.1,
    )
    birder.warmup()
    eff = None
    return birder, eff


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=REPO,
        help="BirdLense repo root (default: parent of scripts/)",
    )
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--backend", default="openvino", choices=("openvino", "torch"))
    ap.add_argument("--sample-frames", type=int, default=8)
    ap.add_argument("--det-conf", type=float, default=0.2)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    root = args.repo_root.resolve()
    if (root / "processor").is_dir():
        proc_root = root / "processor"
        data_root_default = root / "data"
    else:
        proc_root = root / "app/processor"
        data_root_default = root / "app/data"
    global WEIGHTS, DET_PT  # noqa: PLW0603
    WEIGHTS = proc_root / "models/classification/weights"
    DET_PT = proc_root / "models/detection/weights/best.pt"
    proc_src = proc_root / "src"
    if str(proc_src) not in sys.path:
        sys.path.insert(0, str(proc_src))
    db_path = args.db or (data_root_default / "db/birdlense.db")
    data_root = args.data_root or data_root_default
    out_path = args.out or (root / "docs/reports/favorites_ab_benchmark.json")

    if not db_path.is_file():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1
    if not DET_PT.is_file():
        print(f"Detector weights missing: {DET_PT}", file=sys.stderr)
        return 1

    from ultralytics import YOLO

    conn = sqlite3.connect(db_path)
    favorites = conn.execute(
        """
        SELECT id, video_path FROM video
        WHERE favorite = 1 AND deleted_at IS NULL
        ORDER BY id DESC
        """
    ).fetchall()

    detector = YOLO(str(DET_PT))
    birder, eff = _load_classifiers(args.backend)

    rows: list[VideoAbRow] = []
    for vid_id, raw_path in favorites:
        vp = _resolve_video_path(data_root, str(raw_path))
        if vp is None:
            print(f"SKIP {vid_id}: missing file {raw_path}", file=sys.stderr)
            continue
        db_labels = _db_labels(conn, int(vid_id))
        crops = _extract_crops(vp, detector, sample_frames=args.sample_frames, min_conf=args.det_conf)
        b_top, b_raw, b_conf, b_ms, b_jay = _majority_vote(birder, crops, raw_votes=True)
        e_top, _, e_conf, e_ms, e_jay = _majority_vote(eff, crops)
        agree_db = bool(db_labels) and any(_names_match(b_top or "", d) for d in db_labels)
        agree_raw = bool(db_labels) and any(_names_match(b_raw or "", d) for d in db_labels)
        e_absurd = _normalize_name(e_top) in _ABSURD_EFFICIENTNET
        rows.append(
            VideoAbRow(
                video_id=int(vid_id),
                video_path=str(raw_path),
                db_top_species=db_labels,
                n_crops=len(crops),
                birder_top1=b_top,
                birder_raw_top1=b_raw,
                birder_conf=round(b_conf, 4),
                birder_ms_per_crop=round(b_ms, 2),
                efficientnet_top1=e_top,
                efficientnet_conf=round(e_conf, 4),
                efficientnet_ms_per_crop=round(e_ms, 2),
                agree_with_db=agree_db,
                agree_raw_with_db=agree_raw,
                engines_agree=_names_match(b_top or "", e_top or ""),
                birder_jay_rank=b_jay,
                efficientnet_jay_rank=e_jay,
                efficientnet_absurd=e_absurd,
            )
        )

    conn.close()
    n_agree_db = sum(1 for r in rows if r.agree_with_db)
    n_agree_raw = sum(1 for r in rows if r.agree_raw_with_db)
    n_eng_agree = sum(1 for r in rows if r.engines_agree)
    n_eff_absurd = sum(1 for r in rows if r.efficientnet_absurd)
    payload = {
        "backend": args.backend,
        "method": "8 evenly spaced frames, YOLO best.pt largest box crop, openvino classifiers",
        "n_favorites": len(favorites),
        "n_processed": len(rows),
        "birder_gated_agrees_with_db_top": n_agree_db,
        "birder_raw_agrees_with_db_top": n_agree_raw,
        "engines_agree_count": n_eng_agree,
        "efficientnet_absurd_global_species": n_eff_absurd,
        "videos": [asdict(r) for r in rows],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
