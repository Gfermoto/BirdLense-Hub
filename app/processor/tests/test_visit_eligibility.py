"""Tests for visit eligibility helpers."""

import os
import sys
import unittest

app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from app_config.visit_eligibility import (  # noqa: E402
    is_generic_bird_species_name,
    visit_eligible_for_named_species,
)


class TestVisitEligibility(unittest.TestCase):
    def test_generic_bird_labels(self):
        for label in ("Bird", "bird", "Unknown", "Unknown Bird", "generic bird"):
            self.assertTrue(is_generic_bird_species_name(label))

    def test_named_species_not_generic(self):
        self.assertFalse(is_generic_bird_species_name("Great Tit"))
        self.assertFalse(is_generic_bird_species_name("Robin"))

    def test_visit_eligible_includes_catalog_placeholders(self):
        self.assertTrue(
            visit_eligible_for_named_species(species_name="Bird", visit_eligible=True)
        )
        self.assertTrue(
            visit_eligible_for_named_species(species_name="Rodent", visit_eligible=True)
        )
        self.assertFalse(
            visit_eligible_for_named_species(species_name="Unknown", visit_eligible=True)
        )
        self.assertTrue(
            visit_eligible_for_named_species(species_name="Robin", visit_eligible=True)
        )


if __name__ == "__main__":
    unittest.main()
