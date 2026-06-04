"""Tests for NVR object confirm gate."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from object_confirm import (
    detector_bird_score_history,
    padded_median_score,
    track_object_confirmed,
)


class _Cfg:
    def __init__(self, data: dict | None = None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestObjectConfirm(unittest.TestCase):
    def test_median_confirm_weak_frames_one_peak(self):
        cfg = _Cfg(
            {
                "processor.min_confidence_binary_bird": 0.08,
                "processor.object_confirm_threshold": 0.10,
            }
        )
        track = {
            "detector_events": [
                {"label": "Bird", "confidence": 0.05},
                {"label": "Bird", "confidence": 0.12},
                {"label": "Bird", "confidence": 0.09},
            ]
        }
        ok, score, reason = track_object_confirmed(
            app_config=cfg,
            track=track,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "peak_threshold")
        self.assertGreaterEqual(score, 0.10)

    def test_history_zeros_below_min_score(self):
        hist = detector_bird_score_history(
            {"detector_events": [{"label": "Bird", "confidence": 0.05}]},
            min_score=0.08,
        )
        self.assertEqual(hist, [0.0])

    def test_padded_median(self):
        self.assertAlmostEqual(padded_median_score([0.12, 0.14, 0.16]), 0.14, places=3)

    def test_not_confirmed_all_weak(self):
        cfg = _Cfg({"processor.min_confidence_binary_bird": 0.08, "processor.object_confirm_threshold": 0.20})
        track = {"detector_events": [{"label": "Bird", "confidence": 0.09}] * 5}
        ok, _, reason = track_object_confirmed(
            app_config=cfg,
            track=track,
            min_confidence_to_process=0.12,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "below_threshold")


if __name__ == "__main__":
    unittest.main()
