#!/usr/bin/env python3
"""Smoke test Birder EU classifier (onnxruntime or torch) on a bird crop or video frame."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROC_SRC = REPO / "app" / "processor" / "src"
if str(PROC_SRC) not in sys.path:
    sys.path.insert(0, str(PROC_SRC))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", choices=("onnxruntime", "torch"), default="onnxruntime")
    ap.add_argument("--variant", default="convnext_v2_tiny_eu-common256px")
    ap.add_argument(
        "--weights-dir",
        type=Path,
        default=None,
        help="Bundle dir with class_labels.txt (default: weights/{variant}/)",
    )
    ap.add_argument(
        "--video",
        type=Path,
        default=REPO / "app" / "data" / "stress_clips" / "storm_bird.mp4",
    )
    ap.add_argument("--frame", type=int, default=50)
    args = ap.parse_args()

    base = REPO / "app" / "processor" / "models" / "classification"
    wdir = args.weights_dir or (base / args.variant)

    from inference.birder_eu_classifier import load_birder_eu_classifier

    clf = load_birder_eu_classifier(
        str(wdir),
        backend=args.backend,
        variant=args.variant,
        min_confidence=0.1,
        device="cuda:0" if args.backend == "onnxruntime" else None,
    )

    import cv2
    import numpy as np

    if args.video.is_file():
        cap = cv2.VideoCapture(str(args.video))
        cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            print("WARN: video read failed, using synthetic crop")
            crop = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
        else:
            h, w = frame.shape[:2]
            crop = frame[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
    else:
        crop = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)

    out = clf.classify_crop_bgr(crop)
    print(f"backend={args.backend} top1={out.species_name!r} conf={out.top1_confidence:.3f}")
    print(f"entropy={out.entropy:.3f} margin={out.top1_top2_margin:.3f}")
    jay_ids = [i for i, n in clf.names.items() if "jay" in n.lower()]
    print("jay label ids:", [(i, clf.names[i]) for i in jay_ids])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
