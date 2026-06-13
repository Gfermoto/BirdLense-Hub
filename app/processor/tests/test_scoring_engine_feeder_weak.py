"""Regression: weak OpenVINO conf + static feeder birds must survive ScoringEngine."""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from scoring_engine import ScoringEngine, ScoringEngineConfig  # noqa: E402


class TestScoringEngineFeederWeak(unittest.TestCase):
    def _feeder_engine(self) -> ScoringEngine:
        cfg = ScoringEngineConfig(
            enabled=True,
            default_low_threshold=0.10,
            default_high_threshold=0.48,
            calibration_frames=5,
            calibration_low_floor=0.06,
            relaxed_scoring_min_confidence=0.05,
            static_phantom_reject_enabled=False,
        )
        return ScoringEngine(cfg)

    def _static_bird_box(self, conf: float = 0.08) -> dict:
        return {
            "detector_label": "Bird",
            "conf": conf,
            "track_id": 1,
            "crop_coords": (120, 100, 180, 160),
            "box_area_norm": 0.015,
        }

    def test_weak_conf_survives_after_calibration(self):
        eng = self._feeder_engine()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(6):
            eng.filter_boxes([], frame_bgr=frame, frame_index=i)
        self.assertLessEqual(eng.calibration.low_threshold, 0.12)
        kept = eng.filter_boxes([self._static_bird_box(0.08)], frame_bgr=frame, frame_index=7)
        self.assertEqual(len(kept), 1)
        self.assertGreater(eng.last_stats["scoring_review"] + eng.last_stats["scoring_accepted"], 0)

    def test_static_phantom_off_allows_low_motion_bird(self):
        cfg = ScoringEngineConfig(
            enabled=True,
            default_low_threshold=0.38,
            default_high_threshold=0.52,
            calibration_frames=5,
            static_phantom_reject_enabled=True,
            static_phantom_max_conf=0.52,
        )
        eng = ScoringEngine(cfg)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(6):
            eng.filter_boxes([], frame_bgr=frame, frame_index=i)
        kept_phantom_on = eng.filter_boxes([self._static_bird_box(0.10)], frame_bgr=frame, frame_index=7)
        eng2 = self._feeder_engine()
        for i in range(6):
            eng2.filter_boxes([], frame_bgr=frame, frame_index=i)
        kept_phantom_off = eng2.filter_boxes([self._static_bird_box(0.10)], frame_bgr=frame, frame_index=7)
        self.assertEqual(len(kept_phantom_on), 0)
        self.assertEqual(len(kept_phantom_off), 1)


if __name__ == "__main__":
    unittest.main()
