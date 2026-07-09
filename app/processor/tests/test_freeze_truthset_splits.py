"""Synthetic tests for scripts/freeze_truthset_splits.py."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../.."))
_scripts_path = os.path.join(_repo_root, "scripts")
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestFreezeTruthsetSplits(unittest.TestCase):
    def test_freeze_splits_ok(self):
        from freeze_truthset_splits import freeze_truthset_splits

        clips = [
            {"clip_id": "a", "day_night": "day", "weather": "clear"},
            {"clip_id": "b", "day_night": "night", "weather": "rain"},
            {"clip_id": "c", "day_night": "day", "weather": "cloudy"},
            {"clip_id": "d", "day_night": "night", "weather": "rain"},
            {"clip_id": "e", "day_night": "day", "weather": "clear"},
            {"clip_id": "f", "day_night": "night", "weather": "clear"},
        ]
        out = freeze_truthset_splits(
            clips=clips,
            min_clips=6,
            val_ratio=0.2,
        )
        self.assertEqual(out["schema"], "truthset_splits@v1")
        self.assertTrue(out["gates"]["min_clips_ok"])
        self.assertTrue(out["gates"]["coverage_day_night_weather_ok"])
        self.assertTrue(out["gates"]["non_empty_splits_ok"])


if __name__ == "__main__":
    unittest.main()
