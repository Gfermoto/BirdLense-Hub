"""Recording gate motion_immediate contract (#635): trigger → record without lores anchor."""

from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

import processor_bootstrap as bootstrap_mod  # noqa: E402
from detection_scheduler import (  # noqa: E402
    RECORDING_GATE_DETECT_FIRST,
    RECORDING_GATE_MOTION_IMMEDIATE,
    requires_detect_first_before_record,
)


def _motion_immediate_cfg_get(key, default=None):
    values = {
        "video.source": "go2rtc",
        "processor.recording_gate_mode": RECORDING_GATE_MOTION_IMMEDIATE,
        "processor.detect_first_enabled": True,
        "processor.detect_first_triggers": ["opencv", "frigate"],
        "processor.detect_scheduler_enabled": True,
        "processor.detect_scheduler_triggers": ["opencv", "frigate"],
        "detection.track_first_gate_enabled": True,
        "detection.trigger_moratorium_seconds": 0,
        "processor.min_seconds_between_recordings": 0,
    }
    return values.get(key, default)


class TestRecordingGateMotionImmediate(unittest.TestCase):
    def test_requires_detect_first_false_under_motion_immediate(self):
        cfg = {
            "video.source": "go2rtc",
            "processor.recording_gate_mode": RECORDING_GATE_MOTION_IMMEDIATE,
            "processor.detect_first_enabled": True,
        }
        self.assertFalse(
            requires_detect_first_before_record(args=SimpleNamespace(input=None), app_config=cfg)
        )

    def test_birdbox_opencv_trigger_starts_recording_with_zero_lores_hits(self):
        """BirdBox: motion fires, detect_until_confirmed returns None (hits=0) — run() still starts."""

        class _Detector:
            def __init__(self):
                self.pending = 1

            def detect(self):
                if self.pending:
                    self.pending -= 1
                    return True
                raise SystemExit("done")

            def get_triggered_by(self):
                return "opencv"

            def get_triggered_camera(self):
                return "BirdBox"

        class _API:
            def __init__(self):
                self.notify_calls = 0

            def notify_motion(self):
                self.notify_calls += 1

        class _Session:
            def __init__(self):
                self.motion_detector = _Detector()
                self.api = _API()
                self.run_calls = 0
                self.detect_calls = 0
                self.run_kwargs = None
                self.args = SimpleNamespace(input=None)

            def detect_until_confirmed(self, *, camera_id, trigger_source):
                self.detect_calls += 1
                return None

            def run(self, **kwargs):
                self.run_calls += 1
                self.run_kwargs = dict(kwargs)
                return True

        ctx = SimpleNamespace(session=_Session(), file_test=None)
        with patch.object(bootstrap_mod, "check_restart_flag", return_value=None), patch.object(
            bootstrap_mod.app_config,
            "get",
            side_effect=_motion_immediate_cfg_get,
        ), patch.object(bootstrap_mod.time, "sleep", return_value=None):
            bootstrap_mod.run_motion_loop(ctx)

        self.assertEqual(ctx.session.detect_calls, 0)
        self.assertEqual(ctx.session.run_calls, 1)
        self.assertEqual(ctx.session.api.notify_calls, 1)
        self.assertIsNone(ctx.session.run_kwargs.get("detect_first_anchor"))

    def test_detect_first_mode_still_blocks_without_anchor(self):
        """Legacy detect_first gate: no anchor → no run()."""

        def _detect_first_cfg_get(key, default=None):
            values = {
                "video.source": "go2rtc",
                "processor.recording_gate_mode": RECORDING_GATE_DETECT_FIRST,
                "processor.detect_first_enabled": True,
                "processor.detect_first_triggers": ["opencv", "frigate"],
                "detection.trigger_moratorium_seconds": 0,
                "processor.min_seconds_between_recordings": 0,
            }
            return values.get(key, default)

        class _Detector:
            def __init__(self):
                self.pending = 1

            def detect(self):
                if self.pending:
                    self.pending -= 1
                    return True
                raise SystemExit("done")

            def get_triggered_by(self):
                return "opencv"

            def get_triggered_camera(self):
                return "BirdBox"

        class _API:
            def notify_motion(self):
                pass

        class _Session:
            def __init__(self):
                self.motion_detector = _Detector()
                self.api = _API()
                self.run_calls = 0
                self.detect_calls = 0
                self.args = SimpleNamespace(input=None)

            def detect_until_confirmed(self, *, camera_id, trigger_source):
                self.detect_calls += 1
                return None

            def run(self, **kwargs):
                self.run_calls += 1
                return True

        ctx = SimpleNamespace(session=_Session(), file_test=None)
        with patch.object(bootstrap_mod, "check_restart_flag", return_value=None), patch.object(
            bootstrap_mod.app_config,
            "get",
            side_effect=_detect_first_cfg_get,
        ), patch.object(bootstrap_mod.time, "sleep", return_value=None):
            with self.assertRaises(SystemExit):
                bootstrap_mod.run_motion_loop(ctx)

        self.assertEqual(ctx.session.detect_calls, 1)
        self.assertEqual(ctx.session.run_calls, 0)


if __name__ == "__main__":
    unittest.main()
