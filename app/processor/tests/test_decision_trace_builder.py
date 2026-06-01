"""Tests for serialized decision trace rows."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
app_path = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.insert(0, src_path)
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from decision_trace_builder import (  # noqa: E402
    _compact_runtime_signals,
    decision_trace_row,
)


class TestDecisionTraceBuilder(unittest.TestCase):
    def test_keeps_arbitration_evidence_fields(self):
        row = decision_trace_row(
            {
                "track_id": 42,
                "accepted": True,
                "species_name": "Magpie",
                "confidence": 0.77,
                "decision_reason": "absorbed_generic_into_species",
                "arbitration_reason": "absorbed_generic_into_species",
                "decision_reason_before_arbitration": "fallback_bird",
                "reject_reason_code": None,
                "provider_lineage": ["yolo", "frigate", "arbitration"],
                "yolo_track_present": True,
            },
            persisted_to_clip=True,
        )
        self.assertEqual(
            row["arbitration_reason"],
            "absorbed_generic_into_species",
        )
        self.assertEqual(
            row["decision_reason_before_arbitration"],
            "fallback_bird",
        )
        self.assertEqual(
            row["provider_lineage"],
            ["yolo", "frigate", "arbitration"],
        )
        self.assertTrue(row["yolo_track_present"])
        self.assertTrue(row["persisted_to_clip"])

    def test_defaults_for_missing_optional_values(self):
        row = decision_trace_row(
            {
                "track_id": 1,
                "accepted": False,
                "confidence": 0.0,
            },
            persisted_to_clip=False,
        )
        self.assertEqual(row["audio_evidence"], "none")
        self.assertFalse(row["persisted_to_clip"])
        self.assertFalse(row["yolo_track_present"])

    def test_compact_runtime_signals_keeps_only_scalars(self):
        compact = _compact_runtime_signals(
            {
                "yolo_ran": 12,
                "phase": "suspected",
                "debug_payload": {"huge": True},
                "events": [1, 2, 3],
                "long_text": "x" * 200,
            }
        )
        self.assertEqual(compact["yolo_ran"], 12)
        self.assertEqual(compact["phase"], "suspected")
        self.assertNotIn("debug_payload", compact)
        self.assertNotIn("events", compact)
        self.assertNotIn("long_text", compact)


if __name__ == "__main__":
    unittest.main()
