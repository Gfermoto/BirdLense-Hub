"""Frigate trigger salvage must stay review_only (never silent named_accept)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from recording_finalize_parts.salvage import _build_frigate_trigger_review_salvage_row


class _Cfg:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestFrigateSalvageReviewOnly(unittest.TestCase):
    def test_authority_on_still_review_only(self):
        cfg = _Cfg(
            {
                "detection.frigate_species_authority": True,
                "detection.frigate_standalone_missing_score_fallback": 0.72,
            }
        )
        row = _build_frigate_trigger_review_salvage_row(
            {"sub_label": "Great Tit", "confidence": 0.0},
            duration_s=3.0,
            app_config=cfg,
            camera_id="Forest",
        )
        self.assertEqual(row["decision_kind"], "review_only_generic")
        self.assertEqual(row["outcome_bucket"], "review_only")
        self.assertFalse(row["notification_eligible"])
        self.assertFalse(row["visit_eligible"])
        self.assertFalse(bool(row.get("frigate_species_promoted")))
        self.assertEqual(row.get("frigate_prior_label"), "Great Tit")


if __name__ == "__main__":
    unittest.main()
