"""DecisionMaker SoT tests — linear pipeline only (RC3 dual harness removed)."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
app_root = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(src_path)
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from decision_maker import DecisionMaker

import app_config.app_config as _ac_mod


def _default_frames(n=3):
    out = []
    for i in range(n):
        out.append(
            {
                "t": float(i) * 0.1,
                "bbox": [0.10 + i * 0.01, 0.10 + i * 0.01, 0.30 + i * 0.01, 0.30 + i * 0.01],
            }
        )
    return out


def _make_track(
    *,
    detector_label="Bird",
    detector_confidences=None,
    classifier_events=None,
    start_time=0.0,
    end_time=2.0,
    frames=None,
    best_frame_score=7.0,
    key_frames=None,
):
    detector_confidences = detector_confidences or [0.9, 0.9, 0.9]
    classifier_events = classifier_events or []
    if frames is None:
        frames = _default_frames(max(3, len(detector_confidences)))
    track = {
        "start_time": start_time,
        "end_time": end_time,
        "detector_events": [
            {"label": detector_label, "confidence": conf, "t": idx * 0.1}
            for idx, conf in enumerate(detector_confidences)
        ],
        "classifier_events": [],
        "best_frame": None,
        "best_frame_score": best_frame_score,
        "key_frames": key_frames or [],
        "frames": frames,
    }
    for idx, row in enumerate(classifier_events):
        if isinstance(row, dict):
            track["classifier_events"].append(dict(row))
            continue
        name, cls_conf, det_conf = row[0], row[1], row[2]
        ev = {
            "species_name": name,
            "confidence": cls_conf,
            "detector_confidence": det_conf,
            "combined_confidence": det_conf * cls_conf,
            "t": idx * 0.1,
        }
        if len(row) > 3:
            ev["entropy"] = row[3]
        if len(row) > 4:
            ev["top1_top2_margin"] = row[4]
        track["classifier_events"].append(ev)
    return track


def _cfg_get_linear(key, default=None, *, real_get=None):
    if key == "processor.pipeline_mode":
        return "linear"
    if real_get is not None:
        return real_get(key, default)
    return default


class TestDecisionMakerLinear(unittest.TestCase):
    def setUp(self):
        self.decision_maker = DecisionMaker(min_track_duration=0)
        self._real_get = _ac_mod.app_config.get
        self._cfg_patch = patch.object(_ac_mod.app_config, "get")
        self.mock_get = self._cfg_patch.start()

        def _cfg_get(key, default=None):
            return _cfg_get_linear(key, default, real_get=self._real_get)

        self.mock_get.side_effect = _cfg_get

    def tearDown(self):
        self._cfg_patch.stop()

    def test_named_classifier_accepted_species(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 10,
                classifier_events=[("Cardinal", 0.9, 0.9)] * 2,
            )
        }
        results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["species_name"], "Cardinal")
        self.assertEqual(results[0]["decision_reason"], "accepted_species")
        self.assertTrue(results[0].get("visit_eligible"))

    def test_classifier_majority_picks_top_name(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 10,
                classifier_events=(
                    [("Cardinal", 0.9, 0.9)] * 6 + [("Blue Jay", 0.8, 0.9)] * 4
                ),
            )
        }
        results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["species_name"], "Cardinal")

    def test_no_bbox_rejected(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 5,
                classifier_events=[("Cardinal", 0.9, 0.9)] * 2,
                frames=[],
            )
        }
        decisions = self.decision_maker.get_decisions(tracks)
        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0]["accepted"])
        self.assertEqual(decisions[0]["decision_reason"], "rejected_no_bbox")

    def test_deferred_classifier_is_review_only_presence(self):
        tracks = {
            1: _make_track(
                detector_confidences=[0.9] * 5,
                classifier_events=[],
            )
        }
        results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["species_name"], "Bird")
        self.assertIn("deferred", results[0]["decision_reason"])
        self.assertEqual(results[0]["decision_kind"], "review_only_generic")
        self.assertFalse(results[0].get("visit_eligible", True))

    def test_get_decisions_includes_rejected_short_track(self):
        dm = DecisionMaker(min_track_duration=5.0)
        tracks = {
            1: _make_track(
                start_time=0.0,
                end_time=1.0,
                detector_confidences=[0.9] * 3,
                classifier_events=[("Cardinal", 0.9, 0.9)],
            )
        }
        with patch.object(
            _ac_mod.app_config,
            "get",
            side_effect=lambda k, d=None: _cfg_get_linear(k, d, real_get=self._real_get),
        ):
            decisions = dm.get_decisions(tracks)
        self.assertEqual(len(decisions), 1)
        self.assertFalse(decisions[0]["accepted"])

    def test_get_results_sorts_accepted_by_confidence(self):
        tracks = {
            9: _make_track(
                classifier_events=[("Blue Jay", 0.5, 0.9)] * 2,
                detector_confidences=[0.9] * 5,
            ),
            1: _make_track(
                classifier_events=[("Robin", 0.95, 0.9)] * 2,
                detector_confidences=[0.9] * 5,
            ),
            3: _make_track(
                classifier_events=[("Great Tit", 0.8, 0.9)] * 2,
                detector_confidences=[0.9] * 5,
            ),
        }
        results = self.decision_maker.get_results(tracks)
        pairs = [(r["track_id"], r["species_name"]) for r in results]
        self.assertEqual(pairs[0][1], "Robin")
        self.assertEqual(len(pairs), 3)

    def test_dual_mode_still_routes_linear(self):
        """RC3: dual coerced to linear — no legacy cascade."""
        tracks = {
            1: _make_track(classifier_events=[("House Sparrow", 0.85, 0.9)] * 2)
        }

        def _dual(key, default=None):
            if key == "processor.pipeline_mode":
                return "dual"
            return self._real_get(key, default)

        with patch.object(_ac_mod.app_config, "get", side_effect=_dual):
            results = self.decision_maker.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["species_name"], "House Sparrow")
        self.assertEqual(results[0]["decision_reason"], "accepted_species")

    @patch("app_config.app_config.app_config")
    def test_detector_only_weak_bird_is_review_only(self, mock_cfg):
        mock_cfg.get.side_effect = lambda k, default=None: (
            "linear"
            if k == "processor.pipeline_mode"
            else "binary_track_first"
            if k == "detection.persist_mode"
            else default
        )
        dm = DecisionMaker(
            min_track_duration=0,
            min_confidence_to_process=0.5,
            min_confidence_to_store=0.25,
            classifier_fallback_bird=True,
        )
        tracks = {
            1: _make_track(
                detector_confidences=[0.35] * 5,
                classifier_events=[],
            )
        }
        results = dm.get_results(tracks)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["species_name"], "Bird")
        self.assertFalse(results[0].get("visit_eligible", True))


if __name__ == "__main__":
    unittest.main()
