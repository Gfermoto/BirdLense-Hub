"""Classifier hints module tests (#641, ADR #634)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from classifier_hints import apply_classifier_hints, apply_hints_to_rows, collect_hints  # noqa: E402
from classifier_hints.types import HintPayload, HintSource  # noqa: E402


class TestCollectHints(unittest.TestCase):
    def test_collects_frigate_birdnet_ebird(self):
        cfg = {"processor.regional_species": ["Great Tit"]}
        events = [
            {"source": "frigate", "species": "Blue Tit", "confidence": 0.85},
            {"source": "birdnet", "species": "great tit", "confidence": 0.9},
        ]
        hints = collect_hints(camera_id="cam-a", track={}, mqtt_events=events, app_config=cfg)
        sources = {h.source for h in hints}
        self.assertIn(HintSource.FRIGATE_LABEL, sources)
        self.assertIn(HintSource.BIRDNET, sources)
        self.assertIn(HintSource.EBIRD_REGIONAL, sources)

    def test_ignores_frigate_generic_bird_label(self):
        hints = collect_hints(
            camera_id=None,
            track=None,
            mqtt_events=[{"source": "frigate", "label": "bird", "confidence": 0.9}],
            app_config={},
        )
        self.assertEqual(hints, [])

    def test_ignores_frigate_label_from_other_camera(self):
        hints = collect_hints(
            camera_id="BirdBox",
            track=None,
            mqtt_events=[
                {"source": "frigate", "camera": "Forest", "species": "Eurasian Blue Tit", "confidence": 0.95},
                {"source": "birdnet", "species": "great tit", "confidence": 0.8},
            ],
            app_config={},
        )
        self.assertNotIn(HintSource.FRIGATE_LABEL, {h.source for h in hints})
        self.assertIn(HintSource.BIRDNET, {h.source for h in hints})


class TestApplyHints(unittest.TestCase):
    def test_empty_rows_unchanged(self):
        self.assertEqual(apply_hints_to_rows([], [], app_config={}), [])

    def test_birdnet_hint_boosts_confidence(self):
        rows = [
            {
                "species_name": "great tit",
                "confidence": 0.4,
                "detector_confidence": 0.5,
                "classifier_confidence": 0.4,
            }
        ]
        hints = [
            HintPayload(HintSource.BIRDNET, "great tit", 0.08, 0.9, raw_confidence=0.9),
        ]
        out = apply_hints_to_rows(rows, hints, app_config={"detection.classifier_hints_enabled": True})
        self.assertEqual(len(out), 1)
        self.assertGreater(out[0]["confidence"], 0.4)
        self.assertIn("hint_trace", out[0])

    def test_frigate_hint_nudges_top1_over_ambiguous_peer(self):
        rows = [
            {"species_name": "blue tit", "confidence": 0.35, "classifier_confidence": 0.35},
            {"species_name": "great tit", "confidence": 0.36, "classifier_confidence": 0.36},
        ]
        events = [{"source": "frigate", "species": "Blue Tit", "confidence": 0.95}]
        out = apply_classifier_hints(
            rows,
            mqtt_events=events,
            app_config={"detection.classifier_hints_enabled": True},
        )
        blue = next(r for r in out if r["species_name"] == "blue tit")
        great = next(r for r in out if r["species_name"] == "great tit")
        self.assertGreater(blue["confidence"], great["confidence"])
        self.assertIn("hint_trace", blue)

    def test_disabled_passthrough(self):
        rows = [{"species_name": "robin", "confidence": 0.5}]
        hints = [HintPayload(HintSource.BIRDNET, "robin", 0.08, 0.99)]
        out = apply_hints_to_rows(rows, hints, app_config={"detection.classifier_hints_enabled": False})
        self.assertEqual(out[0]["confidence"], 0.5)
        self.assertNotIn("hint_trace", out[0])

    def test_never_creates_rows_without_tracks(self):
        """Hints alone must not synthesize persist rows."""
        events = [
            {"source": "frigate", "species": "Great Tit", "confidence": 0.99},
            {"source": "birdnet", "species": "great tit", "confidence": 0.99},
        ]
        out = apply_classifier_hints([], mqtt_events=events, app_config={})
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
