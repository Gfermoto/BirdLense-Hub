"""Tests for post-fusion rejection accounting."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_post_fusion_rejections import (  # noqa: E402
    collect_post_fusion_rejections,
)


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestRecordingPostFusionRejections(unittest.TestCase):
    """Test rejected trace rows added after fusion drops accepted rows."""

    def test_marks_missing_low_confidence_accepted_track_as_rejected(self):
        """Low confidence accepted row missing after fusion becomes rejected."""
        rows = collect_post_fusion_rejections(
            _Config({"detection.min_confidence_to_store": 0.5}),
            accepted_pre_fusion=[
                {
                    "track_id": 7,
                    "confidence": 0.4,
                    "species_name": "Robin",
                    "visit_eligible": True,
                }
            ],
            persisted_detections=[],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["track_id"], 7)
        self.assertFalse(rows[0]["accepted"])
        self.assertEqual(
            rows[0]["decision_reason"],
            "rejected_post_fusion_below_store_threshold",
        )
        self.assertEqual(rows[0]["decision_kind"], "rejected")
        self.assertEqual(rows[0]["reject_reason_code"], "low_confidence")
        self.assertEqual(rows[0]["trust_band"], "red")

    def test_ignores_rows_persisted_by_fusion_or_above_store_threshold(self):
        """Do not reject persisted, high confidence, or trackless rows."""
        rows = collect_post_fusion_rejections(
            _Config({"detection.min_confidence_to_store": 0.5}),
            accepted_pre_fusion=[
                {"track_id": 1, "confidence": 0.4},
                {"track_id": 2, "confidence": 0.9},
                {"confidence": 0.1},
            ],
            persisted_detections=[{"track_id": 1}],
        )

        self.assertEqual(rows, [])

    def test_skips_binary_track_first_below_store_floor(self):
        rows = collect_post_fusion_rejections(
            _Config(
                {
                    "detection.min_confidence_to_store": 0.5,
                    "detection.persist_mode": "binary_track_first",
                    "processor.min_confidence_to_process": 0.12,
                }
            ),
            accepted_pre_fusion=[
                {
                    "track_id": 9,
                    "confidence": 0.15,
                    "detector_confidence": 0.15,
                    "detector_label": "Bird",
                    "detection_provider": "yolo",
                    "decision_reason": "accepted_binary_track_classifier_uncertain",
                    "frames": [{"bbox": [1, 2, 10, 12]}],
                    "visit_eligible": True,
                }
            ],
            persisted_detections=[],
        )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
