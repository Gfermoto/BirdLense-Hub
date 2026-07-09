"""Weighted species arbiter tests."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from weighted_species_arbiter import (  # noqa: E402
    apply_weighted_species_arbiter,
)


class TestWeightedSpeciesArbiter(unittest.TestCase):
    def test_birdnet_prior_boosts_confidence(self):
        rows = [
            {
                "species_name": "great tit",
                "confidence": 0.4,
                "detector_confidence": 0.5,
                "classifier_confidence": 0.4,
            }
        ]
        mqtt_events = [
            {"source": "birdnet", "species": "great tit", "confidence": 0.9}
        ]
        cfg = {"detection.classifier_hints_enabled": True}
        out = apply_weighted_species_arbiter(
            rows,
            mqtt_events=mqtt_events,
            app_config=cfg,
        )
        self.assertEqual(len(out), 1)
        self.assertGreater(out[0]["confidence"], 0.4)
        self.assertIn("_weighted_arbiter_score", out[0])


if __name__ == "__main__":
    unittest.main()
