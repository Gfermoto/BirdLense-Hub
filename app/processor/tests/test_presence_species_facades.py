"""PresenceRecorder / SpeciesRecognizer facade tests (RC1)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from presence_recorder import (  # noqa: E402
    PresenceRecorder,
    summarize_presence,
    summarize_reliability,
)
from species_recognizer import (  # noqa: E402
    SpeciesRecognizer,
    is_hub_taxonomy_win,
    summarize_taxonomy,
)


class TestProductFacades(unittest.TestCase):
    def test_presence_from_visit_quality(self):
        st = summarize_presence(
            visit_quality={"presence_rows": 3, "persisted_rows": 5},
            video_id=42,
            video_file_ok=True,
        )
        self.assertEqual(st["schema"], "presence_recorder@v1")
        self.assertEqual(st["rows"], 3)
        self.assertTrue(st["db_persist_success"])

    def test_taxonomy_from_visit_quality(self):
        st = summarize_taxonomy(
            visit_quality={
                "hub_taxonomy_wins": 2,
                "named_share_hub": 0.4,
                "auto_accept_rows": 2,
                "review_only_rows": 1,
            },
            recognition_outcomes={"by_kind": {"named_accept": 2}},
        )
        self.assertEqual(st["schema"], "species_recognizer@v1")
        self.assertEqual(st["hub_wins"], 2)
        self.assertEqual(st["outcome_counts"]["named_accept"], 2)

    def test_reliability_namespace(self):
        st = summarize_reliability(
            video_id=1,
            video_file_ok=True,
            finalize_duration_ms=12.5,
            yolo_blind_score=0.1,
            latency_budget_breaches=[],
        )
        self.assertEqual(st["schema"], "reliability@v1")
        self.assertTrue(st["db_persist_success"])
        self.assertEqual(st["post_fusion_persisted"], 1)

    def test_hub_taxonomy_win_helper(self):
        row = {
            "species_name": "Great Tit",
            "decision_kind": "accepted_species",
            "decision_reason": "accepted_species",
            "detection_provider": "yolo",
            "visit_eligible": True,
            "notification_eligible": True,
        }
        self.assertTrue(is_hub_taxonomy_win(row))


    def test_presence_recorder_service(self):
        svc = PresenceRecorder()
        st = svc.summarize(
            visit_quality={"presence_rows": 2, "persisted_rows": 2},
            video_id=1,
            video_file_ok=True,
        )
        self.assertEqual(st["schema"], "presence_recorder@v1")
        rel = svc.reliability(video_id=1, video_file_ok=True, finalize_duration_ms=1.0)
        self.assertEqual(rel["schema"], "reliability@v1")

    def test_species_recognizer_service(self):
        svc = SpeciesRecognizer()
        st = svc.summarize(
            visit_quality={"hub_taxonomy_wins": 1, "auto_accept_rows": 1, "review_only_rows": 0},
            recognition_outcomes={"by_kind": {"named_accept": 1}},
        )
        self.assertEqual(st["schema"], "species_recognizer@v1")
        self.assertEqual(st["hub_wins"], 1)


if __name__ == "__main__":
    unittest.main()
