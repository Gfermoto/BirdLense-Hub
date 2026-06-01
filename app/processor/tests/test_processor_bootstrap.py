import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

import processor_bootstrap as bootstrap_mod  # noqa: E402
from processor_bootstrap import recording_cooldown_remaining  # noqa: E402


class TestProcessorBootstrapCooldown(unittest.TestCase):
    def test_recording_cooldown_remaining_zero_when_disabled(self):
        self.assertEqual(
            recording_cooldown_remaining(
                last_recording_end=100.0,
                cooldown=0.0,
                now_monotonic=104.0,
            ),
            0.0,
        )

    def test_recording_cooldown_remaining_positive_inside_gap(self):
        self.assertEqual(
            recording_cooldown_remaining(
                last_recording_end=100.0,
                cooldown=8.0,
                now_monotonic=103.5,
            ),
            4.5,
        )

    def test_recording_cooldown_remaining_zero_after_gap_elapsed(self):
        self.assertEqual(
            recording_cooldown_remaining(
                last_recording_end=100.0,
                cooldown=8.0,
                now_monotonic=109.0,
            ),
            0.0,
        )

    def test_run_motion_loop_requeues_trigger_when_cooldown_blocks_start(self):
        class _Detector:
            def __init__(self):
                self.pending = 1
                self.requeue_calls = 0

            def detect(self):
                if self.pending > 0:
                    self.pending -= 1
                    return True
                raise SystemExit("detector exhausted")

            def requeue_last_trigger(self):
                self.requeue_calls += 1
                self.pending += 1
                return True

            def get_triggered_by(self):
                return "frigate"

        class _API:
            def __init__(self):
                self.notify_calls = 0
                self.activity_calls = []

            def notify_motion(self):
                self.notify_calls += 1

            def activity_log(self, event_type, data):
                self.activity_calls.append((event_type, dict(data or {})))

        class _Session:
            def __init__(self):
                self.motion_detector = _Detector()
                self.api = _API()
                self.run_calls = 0

            def run_detection_probe_window(self, *, camera_id, trigger_source):
                return True

            def run(self):
                self.run_calls += 1
                return True

        ctx = SimpleNamespace(session=_Session(), file_test=None)
        with patch.object(bootstrap_mod, "check_restart_flag", return_value=None), patch.object(
            bootstrap_mod.app_config,
            "get",
            return_value=8.0,
        ), patch.object(
            bootstrap_mod,
            "recording_cooldown_remaining",
            side_effect=[2.0, 0.0, 0.0],
        ), patch.object(
            bootstrap_mod.time,
            "sleep",
            return_value=None,
        ):
            bootstrap_mod.run_motion_loop(ctx)

        self.assertEqual(ctx.session.motion_detector.requeue_calls, 1)
        self.assertEqual(ctx.session.api.notify_calls, 1)
        self.assertEqual(ctx.session.run_calls, 1)
        self.assertEqual(len(ctx.session.api.activity_calls), 1)
        event_type, payload = ctx.session.api.activity_calls[0]
        self.assertEqual(event_type, "trigger_moratorium")
        self.assertEqual(payload.get("trigger_source"), "frigate")
        self.assertEqual(payload.get("requeued"), True)


if __name__ == '__main__':
    unittest.main()
