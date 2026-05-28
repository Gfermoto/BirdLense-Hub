#!/usr/bin/env python3
"""Compare EU-relevant classifiers on shared crops (Birder vs EfficientNet vs YOLO EU)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
PROC_SRC = REPO / "app" / "processor" / "src"
if str(PROC_SRC) not in sys.path:
    sys.path.insert(0, str(PROC_SRC))

WEIGHTS = REPO / "app" / "processor" / "models" / "classification" / "weights"


@dataclass
class BenchRow:
    engine: str
    backend: str
    ms_per_crop: float
    top1: str | None
    conf: float
    entropy: float
    margin: float
    jay_rank: int | None
    jay_conf: float | None


def _load_crops(video: Path, frames: list[int], n_random: int) -> list[np.ndarray]:
    crops: list[np.ndarray] = []
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return [np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8) for _ in range(n_random)]
    for fi in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        crops.append(frame[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4])
    cap.release()
    while len(crops) < n_random:
        crops.append(np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8))
    return crops


def _jay_stats(names: dict[int, str], probs: np.ndarray | None, top1: str | None) -> tuple[int | None, float | None]:
    jay_ids = [i for i, n in names.items() if "eurasian jay" in n.lower()]
    if not jay_ids:
        return None, None
    if probs is not None:
        best_j = max(jay_ids, key=lambda i: probs[i] if i < len(probs) else 0.0)
        ranked = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
        rank = ranked.index(best_j) + 1 if best_j in ranked else None
        return rank, float(probs[best_j])
    if top1 and "jay" in top1.lower():
        return 1, None
    return None, None


def bench_birder(crops: list[np.ndarray], backend: str) -> BenchRow | None:
    variant = "convnext_v2_tiny_eu-common256px"
    ov_dir = WEIGHTS / f"{variant}_openvino_model"
    torch_dir = WEIGHTS / f"{variant}.pt"
    if backend == "openvino" and not (ov_dir / "openvino_model.xml").is_file():
        return None
    from inference.birder_eu_classifier import load_birder_eu_classifier

    clf = load_birder_eu_classifier(
        str(ov_dir if backend == "openvino" else str(WEIGHTS / f"{variant}_openvino_model")),
        backend=backend,
        variant="convnext_v2_tiny_eu-common256px",
        min_confidence=0.1,
    )
    clf.warmup()
    t0 = time.perf_counter()
    last = None
    for c in crops:
        last = clf.classify_crop_bgr(c)
    ms = (time.perf_counter() - t0) * 1000.0 / len(crops)
    assert last is not None
    jrank, jconf = _jay_stats(clf.names, None, last.species_name)
    return BenchRow("birder_eu", backend, ms, last.species_name, last.top1_confidence, last.entropy, last.top1_top2_margin, jrank, jconf)


def bench_efficientnet(crops: list[np.ndarray], backend: str) -> BenchRow | None:
    base = WEIGHTS / "efficientnet_b2_global_openvino_model"
    if backend == "openvino" and not (base / "openvino_model.xml").is_file() and not (base / "birds_classifier_260.xml").is_file():
        return None
    from inference.efficientnet_b2_classifier import load_efficientnet_b2_classifier

    clf = load_efficientnet_b2_classifier(
        str(base if backend == "openvino" else WEIGHTS),
        backend=backend,
        min_confidence=0.1,
    )
    clf.warmup()
    t0 = time.perf_counter()
    last = None
    for c in crops:
        last = clf.classify_crop_bgr(c)
    ms = (time.perf_counter() - t0) * 1000.0 / len(crops)
    assert last is not None
    jrank, jconf = _jay_stats(clf.id2label, None, last.species_name)
    return BenchRow("efficientnet_b2", backend, ms, last.species_name, last.top1_confidence, last.entropy, last.top1_top2_margin, jrank, jconf)


def bench_yolo(crops: list[np.ndarray]) -> BenchRow | None:
    pt = WEIGHTS / "yolo_eu_best.pt"
    if not pt.is_file():
        return None
    from inference.torch_backend import load_yolo_classifier

    clf = load_yolo_classifier(str(pt), backend="torch")
    t0 = time.perf_counter()
    top1 = None
    conf = 0.0
    names = getattr(clf, "names", {}) or {}
    for c in crops:
        r = clf(c, verbose=False)
        if r and r[0].probs is not None:
            probs = r[0].probs.data.cpu().numpy()
            idx = int(probs.argmax())
            top1 = str(names.get(idx, r[0].names[idx])).replace("_", " ")
            conf = float(probs[idx])
    ms = (time.perf_counter() - t0) * 1000.0 / len(crops)
    jrank, jconf = _jay_stats({int(k): str(v) for k, v in names.items()}, None, top1)
    return BenchRow("yolo_eu", "torch", ms, top1, conf, 0.0, 0.0, jrank, jconf)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", type=Path, default=REPO / "app/data/stress_clips/storm_bird.mp4")
    ap.add_argument("--frames", default="30,50,80,120")
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--out", type=Path, default=REPO / "docs/reports/classifier_eu_benchmark.json")
    args = ap.parse_args()
    frames = [int(x.strip()) for x in args.frames.split(",") if x.strip()]
    crops = _load_crops(args.video, frames, args.repeats)

    rows: list[BenchRow] = []
    for fn in (bench_birder, bench_efficientnet, bench_yolo):
        try:
            if fn is bench_yolo:
                r = fn(crops)
                if r:
                    rows.append(r)
            else:
                for backend in ("openvino", "torch"):
                    r = fn(crops, backend)
                    if r:
                        rows.append(r)
        except Exception as exc:
            print(f"SKIP {fn.__name__}: {exc}", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "video": str(args.video),
        "n_crops": len(crops),
        "results": [asdict(x) for x in rows],
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
