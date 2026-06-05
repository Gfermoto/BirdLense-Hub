"""Tests for linear recording pipeline (detect → classify → reid/behavior → persist)."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from decision_maker import DecisionMaker
from linear_pipeline import (
    STAGE_DETECT_TRACK,
    build_linear_decisions,
    evaluate_track_linear,
    is_linear_pipeline,
)


def _bbox_frames(n=3):
    return [{"t": i * 0.1, "bbox": [0.1, 0.1, 0.3, 0.3]} for i in range(n)]


def _track(*, conf=0.25, species=None, frames=None):
    clf = []
    if species:
        clf = [
            {
                "species_name": species,
                "confidence": 0.55,
                "combined_confidence": 0.55,
                "detector_confidence": conf,
            }
        ]
    return {
        "start_time": 0.0,
        "end_time": 2.5,
        "detector_events": [{"label": "Bird", "confidence": conf}],
        "classifier_events": clf,
        "frames": frames if frames is not None else _bbox_frames(),
        "best_frame": None,
        "best_frame_score": 0.0,
        "key_frames": [],
    }


class _Cfg:
    def __init__(self, data: dict | None = None):
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestLinearPipeline(unittest.TestCase):
    def test_is_linear_default_legacy_when_unset(self):
        self.assertFalse(is_linear_pipeline(_Cfg({})))
        self.assertTrue(is_linear_pipeline(_Cfg({"processor.pipeline_mode": "linear"})))

    def test_weak_bird_with_bbox_persists(self):
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.min_confidence_binary_bird": 0.08,
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.12),
            min_track_duration=0.5,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])
        self.assertEqual(ev["decision_reason"], "track_first_persist")
        self.assertEqual(ev["out_species"], "Bird")
        self.assertTrue(ev["visit_eligible"])

    def test_static_like_track_not_blocked_by_linear(self):
        """Linear has no static_pinned — forest-style weak conf still passes floor."""
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.min_confidence_binary_bird": 0.08,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.09, frames=_bbox_frames(8)),
            min_track_duration=1.0,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])

    def test_no_bbox_rejected(self):
        cfg = _Cfg({"processor.min_confidence_binary_bird": 0.08})
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.5, frames=[]),
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertFalse(ev["accepted"])
        self.assertEqual(ev["decision_reason"], "rejected_no_bbox")

    def test_named_species_from_classifier(self):
        cfg = _Cfg(
            {
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
            }
        )
        ev = evaluate_track_linear(
            app_config=cfg,
            track=_track(conf=0.4, species="Eurasian Jay"),
            min_track_duration=0.0,
            min_confidence_to_process=0.12,
        )
        self.assertTrue(ev["accepted"])
        self.assertEqual(ev["out_species"], "Eurasian Jay")
        self.assertEqual(ev["decision_reason"], "accepted_species")

    def test_build_linear_decisions_via_decision_maker(self):
        dm = DecisionMaker(min_track_duration=0.5, min_confidence_to_process=0.12)
        cfg = _Cfg(
            {
                "processor.pipeline_mode": "linear",
                "processor.min_confidence_binary_bird": 0.08,
                "processor.classifier_best_guess_min_confidence": 0.10,
                "processor.birder_eu_min_confidence": 0.15,
            }
        )
        tracks = {7: _track(conf=0.15)}
        rows = build_linear_decisions(dm, tracks, cfg)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["accepted"])
        self.assertEqual(rows[0]["pipeline_stage"], STAGE_DETECT_TRACK)

    def test_get_decisions_routes_linear(self):
        dm = DecisionMaker(min_track_duration=0.0, min_confidence_to_process=0.12)
        mock_cfg = MagicMock()
        mock_cfg.get.side_effect = lambda k, d=None: {
            "processor.pipeline_mode": "linear",
            "processor.min_confidence_binary_bird": 0.08,
            "processor.classifier_best_guess_min_confidence": 0.10,
            "processor.birder_eu_min_confidence": 0.15,
        }.get(k, d)

        with unittest.mock.patch("app_config.app_config.app_config", mock_cfg):
            rows = dm.get_decisions({1: _track(conf=0.2)})
        self.assertTrue(rows[0]["accepted"])


if __name__ == "__main__":
    unittest.main()
