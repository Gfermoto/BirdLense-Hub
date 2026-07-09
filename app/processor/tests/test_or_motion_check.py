import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from motion_detectors.or_motion import OrMotionDetector  # noqa: E402


class _StubDetector:
    def __init__(self, fires: bool):
        self._fires = fires

    def check(self):
        return self._fires


class TestOrMotionDetectorCheck(unittest.TestCase):
    def test_check_sets_triggered_by(self):
        det = OrMotionDetector(
            named_detectors=[
                ("opencv", _StubDetector(False)),
                ("frigate", _StubDetector(True)),
            ]
        )
        self.assertTrue(det.check())
        self.assertEqual(det.get_triggered_by(), "frigate")

    def test_check_returns_false_when_idle(self):
        det = OrMotionDetector(
            named_detectors=[
                ("opencv", _StubDetector(False)),
                ("frigate", _StubDetector(False)),
            ]
        )
        self.assertFalse(det.check())


if __name__ == "__main__":
    unittest.main()
