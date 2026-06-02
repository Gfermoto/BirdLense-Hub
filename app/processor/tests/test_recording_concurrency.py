import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_concurrency import RecordingConcurrency, concurrent_recording_enabled  # noqa: E402


class TestRecordingConcurrency(unittest.TestCase):
    def test_try_register_blocks_same_camera(self):
        reg = RecordingConcurrency()
        self.assertTrue(reg.try_register("Forest"))
        self.assertFalse(reg.try_register("Forest"))
        reg.unregister("Forest")
        self.assertTrue(reg.try_register("Forest"))

    def test_parallel_cameras(self):
        reg = RecordingConcurrency()
        self.assertTrue(reg.try_register("Forest"))
        self.assertTrue(reg.try_register("BirdBox"))
        self.assertTrue(reg.any_active())
        reg.unregister("BirdBox")
        self.assertTrue(reg.is_active("Forest"))

    def test_concurrent_recording_enabled_default_multi_cam(self):
        cfg = type("Cfg", (), {"get": lambda self, key, default=None: default})()
        self.assertTrue(concurrent_recording_enabled(cfg, camera_count=2))
        self.assertFalse(concurrent_recording_enabled(cfg, camera_count=1))

    def test_concurrent_recording_enabled_explicit_off(self):
        class Cfg:
            def get(self, key, default=None):
                if key == "processor.concurrent_recording_enabled":
                    return False
                return default

        self.assertFalse(concurrent_recording_enabled(Cfg(), camera_count=3))


if __name__ == "__main__":
    unittest.main()
