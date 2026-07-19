"""Unit tests for runtime_contract primary_signal / threshold_path."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from runtime_contract import (
    apply_runtime_contract,
    infer_primary_signal,
    infer_threshold_path,
)


class TestRuntimeContract(unittest.TestCase):
    def test_uncertain_species_primary_is_classifier_review(self):
        row = {
            "decision_kind": "review_only_uncertain_species",
            "decision_reason": "accepted_binary_track_classifier_uncertain",
            "detection_provider": "yolo",
            "classifier_species_name": "Eurasian Jay",
            "classifier_needs_review": True,
        }
        self.assertEqual(infer_primary_signal(row), "species_classifier_review")
        self.assertEqual(infer_threshold_path(row), "classifier_threshold_review")

    def test_accepted_species_without_review_is_classifier(self):
        row = {
            "decision_kind": "accepted_species",
            "decision_reason": "accepted_species",
            "detection_provider": "yolo",
            "classifier_species_name": "Great Tit",
            "classifier_needs_review": False,
        }
        self.assertEqual(infer_primary_signal(row), "species_classifier")
        self.assertEqual(infer_threshold_path(row), "classifier_threshold")

    def test_accepted_species_with_needs_review_is_review_signal(self):
        row = {
            "decision_kind": "accepted_species",
            "detection_provider": "yolo",
            "classifier_needs_review": True,
            "classifier_species_name": "Great Tit",
        }
        self.assertEqual(infer_primary_signal(row), "species_classifier_review")
        out = apply_runtime_contract(dict(row))
        self.assertEqual(out["primary_signal"], "species_classifier_review")


if __name__ == "__main__":
    unittest.main()
