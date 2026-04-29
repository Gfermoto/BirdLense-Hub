"""Тесты контракта имён классов бинарного детектора (#368)."""

import logging
import os
import sys
import unittest


current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)


class TestWeightContract(unittest.TestCase):
    def test_coerce_names_dict(self):
        from inference.weight_contract import coerce_detector_names

        self.assertEqual(
            coerce_detector_names({0: "Bird", 1: "Rodent"}),
            {0: "Bird", 1: "Rodent"},
        )

    def test_validate_warn_missing_scope(self):
        from inference.weight_contract import validate_detector_weight_contract

        log = logging.getLogger("test_validate_warn_missing_scope")
        with self.assertLogs(log, level="WARNING") as cm:
            validate_detector_weight_contract(
                {0: "Bird"},
                {"Bird", "Rodent"},
                "warn",
                log,
            )
        self.assertTrue(any("Rodent" in x for x in cm.output))
        self.assertTrue(
            any("TROUBLESHOOTING.md#detector-weight-contract-mismatch" in x for x in cm.output)
        )

    def test_validate_off_skips_checks(self):
        from inference.weight_contract import validate_detector_weight_contract

        log = logging.getLogger("test_validate_off_skips_checks")
        validate_detector_weight_contract(
            {0: "Bird"},
            {"Bird", "Rodent"},
            "off",
            log,
        )

    def test_validate_enforce_raises(self):
        from inference.weight_contract import validate_detector_weight_contract

        log = logging.getLogger("test_validate_enforce_raises")
        with self.assertRaises(ValueError) as ctx:
            validate_detector_weight_contract(
                {0: "Bird"},
                {"Bird", "Rodent"},
                "enforce",
                log,
            )
        self.assertIn("TROUBLESHOOTING.md#detector-weight-contract-mismatch", str(ctx.exception))

    def test_background_in_scope_raises_enforce(self):
        from inference.weight_contract import validate_detector_weight_contract

        log = logging.getLogger("test_background_in_scope_raises_enforce")
        with self.assertRaises(ValueError):
            validate_detector_weight_contract(
                {0: "Bird", 1: "Rodent", 2: "Background"},
                {"Bird", "Background"},
                "enforce",
                log,
            )

    def test_validate_enforce_three_class_weights_ok(self):
        """3-class детектор: модель содержит Background, scope только Bird+Rodent (#368)."""
        from inference.weight_contract import validate_detector_weight_contract

        log = logging.getLogger("test_validate_enforce_three_class_weights_ok")
        validate_detector_weight_contract(
            {0: "Bird", 1: "Rodent", 2: "Background"},
            {"Bird", "Rodent"},
            "enforce",
            log,
        )


class TestDetectorLabels(unittest.TestCase):
    def test_normalize_matches_epic(self):
        from detector_labels import normalize_detector_label

        self.assertEqual(normalize_detector_label("bird"), "Bird")
        self.assertEqual(normalize_detector_label("Squirrel"), "Rodent")
        self.assertEqual(normalize_detector_label("Background"), "Background")
        self.assertEqual(normalize_detector_label("background"), "Background")


if __name__ == "__main__":
    unittest.main()
