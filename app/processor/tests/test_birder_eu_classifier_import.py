"""Regression: birder_eu_classifier must import without NameError (#610 hotfix)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))


class TestBirderEuClassifierImport(unittest.TestCase):
    def test_module_imports(self):
        from inference.birder_eu_classifier import BirderEuClassifier  # noqa: F401

        self.assertTrue(callable(BirderEuClassifier))


if __name__ == "__main__":
    unittest.main()
