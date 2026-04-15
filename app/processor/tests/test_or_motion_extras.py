"""OrMotionDetector: extras (напр. триггер весов) между Frigate и OpenCV."""
import os
import sys
import threading
import time
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from motion_detectors.or_motion import OrMotionDetector


class _Primary:
    def __init__(self):
        self._e = threading.Event()
        self.recent_calls = []

    def check_pending(self):
        return False

    def get_triggered_camera(self):
        return 'cam1'

    def has_recent_activity(self, camera=None, max_age_seconds=0, min_confidence=0.0):
        self.recent_calls.append((camera, max_age_seconds, min_confidence))
        return camera == 'cam1' and max_age_seconds == 6 and min_confidence == 0.0


class _Extra:
    def __init__(self):
        self._e = threading.Event()

    def check_pending(self):
        if self._e.is_set():
            self._e.clear()
            return True
        return False

    def fire(self):
        self._e.set()


class _Additional:
    def check_pending(self):
        return False


class TestOrMotionExtras(unittest.TestCase):
    def test_extra_triggers_before_additional(self):
        primary = _Primary()
        extra = _Extra()
        add = _Additional()
        or_det = OrMotionDetector(primary=primary, additional=add, extras=[extra])

        def _later():
            time.sleep(0.08)
            extra.fire()

        threading.Thread(target=_later, daemon=True).start()
        t0 = time.time()
        self.assertTrue(or_det.detect())
        self.assertLess(time.time() - t0, 2.0)
        self.assertTrue(or_det.get_triggered_camera() is None)

    def test_has_recent_frigate_activity_delegates_to_primary(self):
        primary = _Primary()
        or_det = OrMotionDetector(primary=primary, additional=None, extras=[])
        self.assertTrue(
            or_det.has_recent_frigate_activity(
                camera='cam1',
                max_age_seconds=6,
                min_confidence=0.0,
            )
        )
        self.assertEqual(primary.recent_calls, [('cam1', 6, 0.0)])


if __name__ == '__main__':
    unittest.main()
