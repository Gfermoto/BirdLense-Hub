import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from recording_session_policy import effective_frigate_hold_seconds  # noqa: E402


class TestRecordingSessionPolicy(unittest.TestCase):
    def test_opencv_trigger_disables_frigate_hold_by_default(self):
        self.assertEqual(
            effective_frigate_hold_seconds(6.0, "opencv"),
            0.0,
        )

    def test_frigate_trigger_keeps_hold(self):
        self.assertEqual(
            effective_frigate_hold_seconds(6.0, "frigate"),
            6.0,
        )

    def test_opencv_with_flag_off_allows_hold(self):
        cfg = {"processor.frigate_hold_only_when_frigate_trigger": False}
        self.assertEqual(
            effective_frigate_hold_seconds(6.0, "opencv", cfg=cfg),
            6.0,
        )


if __name__ == "__main__":
    unittest.main()
