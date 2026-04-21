import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from decision_maker import DecisionMaker  # noqa: E402


class TestDecisionMakerRuntimeProfile(unittest.TestCase):
    def test_apply_and_reset_runtime_overrides(self):
        dm = DecisionMaker(
            min_track_duration=1.0,
            min_confidence_to_process=0.38,
        )

        dm.apply_runtime_overrides(
            {
                "min_track_duration": 0.7,
                "min_confidence_to_process": 0.32,
            }
        )
        self.assertEqual(dm.min_track_duration, 0.7)
        self.assertEqual(dm.min_confidence_to_process, 0.32)

        dm.reset_runtime_overrides()
        self.assertEqual(dm.min_track_duration, 1.0)
        self.assertEqual(dm.min_confidence_to_process, 0.38)


if __name__ == "__main__":
    unittest.main()
