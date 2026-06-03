"""Smoke: concurrent per-camera trigger path (#593)."""

from __future__ import annotations

import sys
import threading
import time
import unittest

import os

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from recording_concurrency import RecordingConcurrency  # noqa: E402


class TestConcurrentRecordingSmoke(unittest.TestCase):
    def test_second_camera_starts_while_first_active(self):
        """Camera B session thread starts while A is registered (concurrent path)."""
        reg = RecordingConcurrency()
        started_b = threading.Event()
        release_a = threading.Event()

        self.assertTrue(reg.try_register("camera_a"))

        def cam_a_session():
            release_a.wait(timeout=5)

        def cam_b_session():
            started_b.set()

        thread_a = threading.Thread(target=cam_a_session, name="rec-a")
        thread_b = threading.Thread(target=cam_b_session, name="rec-b")

        thread_a.start()
        time.sleep(0.05)
        # concurrent path: B registers while A active
        other_active = reg.any_active()
        self.assertTrue(other_active)
        self.assertTrue(reg.try_register("camera_b"))
        snap = reg.snapshot(exclude="camera_b")
        self.assertIn("camera_a", snap["peer_cameras"])
        thread_b.start()
        self.assertTrue(started_b.wait(timeout=2))
        release_a.set()
        thread_a.join(timeout=2)
        thread_b.join(timeout=2)
        reg.unregister("camera_a")
        reg.unregister("camera_b")

    def test_same_camera_deferred_when_busy(self):
        reg = RecordingConcurrency()
        self.assertTrue(reg.try_register("Forest"))
        self.assertFalse(reg.try_register("Forest"))
        reg.unregister("Forest")
        self.assertTrue(reg.try_register("Forest"))


if __name__ == "__main__":
    unittest.main()
