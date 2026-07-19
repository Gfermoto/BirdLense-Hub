"""RC7: Birder open-set must not skip Unknown to force a named label."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from inference.birder_eu_classifier import BirderEuClassifier  # noqa: E402


class TestBirderOpenSet(unittest.TestCase):
    def test_unknown_argmax_is_not_overridden_by_named(self):
        clf = BirderEuClassifier.__new__(BirderEuClassifier)
        clf.unknown_label = "Unknown Bird"
        clf.min_confidence = 0.05
        clf._allowed_ids = {0, 1, 2}
        clf.id2label = {0: "Unknown Bird", 1: "Great Tit", 2: "Eurasian Jay"}
        # Unknown has highest mass; previously code preferred named and would pick Great Tit.
        probs = np.array([0.55, 0.30, 0.15], dtype=np.float64)
        clf._infer_probs = MagicMock(return_value=probs)  # type: ignore[method-assign]
        clf._softmax = lambda x: x  # unused when _infer_probs mocked

        out = clf.classify_crop_bgr(np.zeros((64, 64, 3), dtype=np.uint8))
        self.assertEqual(out.species_name, "Unknown Bird")
        self.assertAlmostEqual(float(out.top1_confidence), 0.55, places=3)

    def test_named_wins_when_argmax_named(self):
        clf = BirderEuClassifier.__new__(BirderEuClassifier)
        clf.unknown_label = "Unknown Bird"
        clf.min_confidence = 0.05
        clf._allowed_ids = {0, 1, 2}
        clf.id2label = {0: "Unknown Bird", 1: "Great Tit", 2: "Eurasian Jay"}
        probs = np.array([0.20, 0.60, 0.20], dtype=np.float64)
        clf._infer_probs = MagicMock(return_value=probs)  # type: ignore[method-assign]

        out = clf.classify_crop_bgr(np.zeros((64, 64, 3), dtype=np.uint8))
        self.assertEqual(out.species_name, "Great Tit")


if __name__ == "__main__":
    unittest.main()
