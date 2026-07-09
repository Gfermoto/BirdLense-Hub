"""SOTA-12 tracker preset registry."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from tracker_registry import (  # noqa: E402
    TRACKER_PRESETS,
    list_tracker_presets,
    resolve_tracker_preset,
)


class TestTrackerRegistry(unittest.TestCase):
    def test_list_presets_includes_bytetrack_and_botsort(self):
        ids = {p["id"] for p in list_tracker_presets()}
        self.assertIn("bytetrack_birdlense", ids)
        self.assertIn("botsort_birdlense", ids)

    def test_resolve_botsort_preset_to_file(self):
        path = resolve_tracker_preset("botsort_birdlense")
        self.assertTrue(os.path.isfile(path), path)
        self.assertIn("botsort_birdlense.yaml", path)

    def test_unknown_falls_through_to_tracker_paths(self):
        self.assertEqual(resolve_tracker_preset("botsort.yaml"), "botsort.yaml")

    def test_preset_types(self):
        self.assertEqual(TRACKER_PRESETS["botsort_birdlense"].tracker_type, "botsort")


if __name__ == "__main__":
    unittest.main()
