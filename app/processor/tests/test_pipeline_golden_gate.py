"""Golden Gate: ScoringEngine F1 on manifest (synthetic + optional real clips)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from scoring_engine import DecisionZone, ScoringEngine, ScoringEngineConfig  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
SYNTH_MANIFEST = REPO_ROOT / "app/data/datasets/golden_v2/manifest.synthetic.json"
REAL_MANIFEST = REPO_ROOT / "app/data/datasets/golden_v2/manifest.json"
MIN_F1 = float(os.environ.get("GOLDEN_GATE_MIN_F1", "0.7"))


def _probes_for_clip(clip: dict) -> list:
    """Synthetic probes when manifest has only clip labels (prod mining)."""
    if clip.get("probes"):
        return clip["probes"]
    if clip.get("is_bird"):
        raw = 0.58 if int(clip.get("yolo_raw") or 0) > 0 else 0.52
        return [{"raw_conf": raw, "expect": "accept"}]
    if int(clip.get("yolo_raw") or 0) > 0:
        return [{"raw_conf": 0.36, "expect": "reject"}]
    return [{"raw_conf": 0.28, "expect": "reject"}]


def _clip_level_prediction(eng: ScoringEngine, clip: dict) -> bool:
    """True if any probe accepted as bird."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    eng.reset()
    for i in range(max(8, int(eng.cfg.calibration_frames))):
        eng.filter_boxes([], frame_bgr=frame, frame_index=i)
    probes = _probes_for_clip(clip)
    if probes:
        for i, probe in enumerate(probes):
            box = {
                "detector_label": "Bird",
                "conf": float(probe.get("raw_conf", 0.3)),
                "track_id": i + 1,
                "crop_coords": (80, 80, 180, 180),
                "box_area_norm": 0.015,
            }
            expect = str(probe.get("expect") or "")
            kept = eng.filter_boxes([box], frame_bgr=frame, frame_index=100 + i)
            accepted = [
                b
                for b in kept
                if str(b.get("detector_label") or "") == "Bird"
                and not b.get("scoring_review_only")
            ]
            if expect == "reject":
                if accepted:
                    return True
                continue
            if expect == "review_or_accept" and kept:
                return True
            if expect == "accept" and accepted:
                return True
        return False
    return False


def _evaluate_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = ScoringEngineConfig(
        enabled=True,
        calibration_frames=8,
        weight_conf=1.0,
        weight_motion=0.0,
        weight_shape=0.0,
        weight_background=0.0,
        default_low_threshold=0.38,
        default_high_threshold=0.52,
    )
    eng = ScoringEngine(cfg)
    tp = fp = fn = tn = 0
    for clip in data.get("clips") or []:
        pred_bird = _clip_level_prediction(eng, clip)
        actual_bird = bool(clip.get("is_bird"))
        if pred_bird and actual_bird:
            tp += 1
        elif pred_bird and not actual_bird:
            fp += 1
        elif not pred_bird and actual_bird:
            fn += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec, "f1": f1}


class TestPipelineGoldenGate(unittest.TestCase):
    def test_synthetic_manifest_f1_gate(self):
        self.assertTrue(SYNTH_MANIFEST.is_file(), f"missing {SYNTH_MANIFEST}")
        metrics = _evaluate_manifest(SYNTH_MANIFEST)
        self.assertGreaterEqual(
            metrics["f1"],
            MIN_F1,
            f"Golden Gate failed: {metrics} (min F1={MIN_F1})",
        )

    def test_real_manifest_f1_gate(self):
        if not REAL_MANIFEST.is_file():
            self.skipTest("real golden_v2 manifest not built")
        data = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
        clips = data.get("clips") or []
        if not clips:
            self.skipTest("real manifest empty — run generate_golden_dataset_v2.py on prod DB")
        metrics = _evaluate_manifest(REAL_MANIFEST)
        self.assertGreaterEqual(metrics["f1"], MIN_F1, f"real manifest: {metrics}")


if __name__ == "__main__":
    unittest.main()
