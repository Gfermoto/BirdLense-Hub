"""Unit tests for SOTA 2.0 ScoringEngine."""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from scoring_engine import DecisionZone, ScoringEngine, ScoringEngineConfig  # noqa: E402


class TestScoringEngine(unittest.TestCase):
    def _engine(self) -> ScoringEngine:
        cfg = ScoringEngineConfig(
            enabled=True,
            default_low_threshold=0.38,
            default_high_threshold=0.52,
            calibration_frames=5,
        )
        return ScoringEngine(cfg)

    def _box(self, conf: float = 0.5) -> dict:
        return {
            "detector_label": "Bird",
            "conf": conf,
            "track_id": 1,
            "crop_coords": (100, 100, 200, 200),
            "box_area_norm": 0.02,
        }

    def test_high_conf_accepted(self):
        eng = self._engine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(6):
            eng.filter_boxes([], frame_bgr=frame, frame_index=i)
        kept = eng.filter_boxes([self._box(0.62)], frame_bgr=frame, frame_index=7)
        self.assertEqual(len(kept), 1)
        self.assertEqual(eng.last_stats["scoring_accepted"], 1)

    def test_low_conf_rejected(self):
        eng = self._engine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(6):
            eng.filter_boxes([], frame_bgr=frame, frame_index=i)
        kept = eng.filter_boxes([self._box(0.25)], frame_bgr=frame, frame_index=7)
        self.assertEqual(len(kept), 0)
        self.assertGreater(eng.last_stats["scoring_rejected"], 0)

    def test_relaxed_small_object_survives_scoring_reject(self):
        eng = self._engine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(6):
            eng.filter_boxes([], frame_bgr=frame, frame_index=i)
        box = self._box(0.25)
        box["relaxed_small_object"] = True
        kept = eng.filter_boxes([box], frame_bgr=frame, frame_index=7)
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0].get("scoring_review_only"))
        self.assertEqual(eng.last_stats["scoring_review"], 1)

    def test_frigate_prior_boost(self):
        eng = self._engine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(6):
            eng.filter_boxes([self._box(0.4)], frame_bgr=frame, frame_index=i, frigate_prior_active=False)
        d0 = eng.decide(self._box(0.4), frame_bgr=frame, frigate_prior_active=False)
        d1 = eng.decide(self._box(0.4), frame_bgr=frame, frigate_prior_active=True)
        self.assertGreater(d1.breakdown.final_score, d0.breakdown.final_score)

    def test_auto_calibration_runs(self):
        eng = self._engine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(8):
            eng.filter_boxes([], frame_bgr=frame, frame_index=i)
        self.assertTrue(eng.calibration.calibrated)


if __name__ == "__main__":
    unittest.main()
