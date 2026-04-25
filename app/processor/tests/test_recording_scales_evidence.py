"""Tests for recording scales evidence helpers."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_scales_evidence import estimate_recording_scales_delta  # noqa: E402


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestRecordingScalesEvidence(unittest.TestCase):
    def test_skips_audio_only_detections(self):
        cfg = _Config(
            {
                "integrations.scales.enabled": True,
                "integrations.scales.weight_estimate_enabled": True,
            }
        )
        delta, evidence = estimate_recording_scales_delta(
            cfg,
            [{"source": "audio"}],
            scales_topic_arg="scales/weight",
            data_dir="/tmp",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        )
        self.assertIsNone(delta)
        self.assertEqual(evidence, {})

    def test_estimates_delta_and_evidence_for_visual_detection(self):
        cfg = _Config(
            {
                "integrations.scales.enabled": True,
                "integrations.scales.weight_estimate_enabled": True,
                "integrations.scales.min_delta_kg_for_estimate": "0.012",
                "integrations.scales.estimate_require_consecutive_spike": False,
            }
        )
        with patch("scale_sample_log.estimate_weight_delta_kg", return_value=(0.023, 4)) as estimator:
            delta, evidence = estimate_recording_scales_delta(
                cfg,
                [{"source": "video"}],
                scales_topic_arg="scales/weight",
                data_dir="/tmp",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
        self.assertEqual(delta, 0.023)
        self.assertEqual(evidence["estimated_delta_kg"], 0.023)
        self.assertEqual(evidence["sample_count"], 4)
        self.assertEqual(evidence["min_delta_kg"], 0.012)
        estimator.assert_called_once()


if __name__ == "__main__":
    unittest.main()
