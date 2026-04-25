"""Tests for recording notification policy helpers."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_notify_policy import (  # noqa: E402
    notify_suppression_reason,
    resolve_min_confidence_to_notify,
)


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class TestRecordingNotifyPolicy(unittest.TestCase):
    def test_resolve_min_confidence_to_notify_falls_back_to_process_threshold(self):
        cfg = _Config(
            {
                "processor.min_confidence_to_notify": "",
                "processor.min_confidence_to_process": 0.42,
            }
        )
        self.assertEqual(resolve_min_confidence_to_notify(cfg), 0.42)

    def test_notify_suppression_reason_blocks_ineligible_kind_and_low_confidence(self):
        self.assertEqual(
            notify_suppression_reason({"notification_eligible": False}, 0.3),
            "ineligible",
        )
        self.assertEqual(
            notify_suppression_reason({"decision_kind": "review_only_generic"}, 0.3),
            "ineligible",
        )
        self.assertEqual(
            notify_suppression_reason({"confidence": 0.2}, 0.3),
            "low_confidence",
        )
        self.assertIsNone(
            notify_suppression_reason({"confidence": 0.8, "decision_kind": "accepted_species"}, 0.3),
        )


if __name__ == "__main__":
    unittest.main()
