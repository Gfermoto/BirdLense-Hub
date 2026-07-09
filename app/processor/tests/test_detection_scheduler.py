"""Detection scheduler trigger gating tests."""

import os
import sys
import unittest
from types import SimpleNamespace

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from detect_first import is_valid_detect_first_anchor  # noqa: E402
from detection_scheduler import (  # noqa: E402
    RECORDING_GATE_DETECT_FIRST,
    RECORDING_GATE_MOTION_IMMEDIATE,
    requires_detect_first_before_record,
    resolve_recording_gate_mode,
    should_run_probe,
    trigger_requires_detect_first,
)


class TestDetectionScheduler(unittest.TestCase):
    def test_probe_enabled_for_configured_trigger(self):
        cfg = {
            "video.source": "file",
            "processor.detect_scheduler_enabled": True,
            "processor.detect_scheduler_triggers": ["frigate", "scales"],
            "detection.track_first_gate_enabled": False,
        }
        self.assertTrue(
            should_run_probe(trigger_source="frigate", app_config=cfg)
        )
        self.assertFalse(
            should_run_probe(trigger_source="opencv", app_config=cfg)
        )

    def test_probe_enabled_for_opencv_in_default_triggers(self):
        cfg = {
            "video.source": "file",
            "processor.detect_scheduler_enabled": True,
            "processor.detect_scheduler_triggers": ["opencv", "frigate", "scales"],
        }
        self.assertTrue(
            should_run_probe(trigger_source="opencv", app_config=cfg)
        )

    def test_probe_opencv_forced_when_track_first_and_legacy_triggers(self):
        """Legacy user_config without opencv still probes when track-first gate is on."""
        cfg = {
            "video.source": "file",
            "processor.detect_scheduler_enabled": True,
            "processor.detect_scheduler_triggers": ["frigate", "scales"],
            "detection.track_first_gate_enabled": True,
        }
        self.assertTrue(
            should_run_probe(trigger_source="opencv", app_config=cfg)
        )

    def test_probe_disabled_globally(self):
        cfg = {"processor.detect_scheduler_enabled": False}
        self.assertFalse(
            should_run_probe(trigger_source="frigate", app_config=cfg)
        )


class TestDetectFirstContract(unittest.TestCase):
    def test_is_valid_anchor_requires_track_and_norm_bbox(self):
        self.assertFalse(is_valid_detect_first_anchor(None))
        self.assertFalse(is_valid_detect_first_anchor({"track_id": 1}))
        self.assertTrue(
            is_valid_detect_first_anchor({"track_id": 7, "bbox": [0.1, 0.2, 0.3, 0.4]})
        )

    def test_motion_immediate_default_skips_detect_first_gate(self):
        cfg = {"video.source": "go2rtc"}
        self.assertEqual(resolve_recording_gate_mode(cfg), RECORDING_GATE_MOTION_IMMEDIATE)
        self.assertFalse(requires_detect_first_before_record(args=SimpleNamespace(input=None), app_config=cfg))

    def test_detect_first_mode_restores_go2rtc_gate(self):
        cfg = {
            "video.source": "go2rtc",
            "processor.recording_gate_mode": RECORDING_GATE_DETECT_FIRST,
        }
        self.assertTrue(requires_detect_first_before_record(args=SimpleNamespace(input=None), app_config=cfg))
        cfg_off = {
            "video.source": "go2rtc",
            "processor.recording_gate_mode": RECORDING_GATE_DETECT_FIRST,
            "processor.detect_first_enabled": False,
        }
        self.assertFalse(requires_detect_first_before_record(args=SimpleNamespace(input=None), app_config=cfg_off))
        self.assertFalse(
            requires_detect_first_before_record(
                args=SimpleNamespace(input="/tmp/x.mp4"),
                app_config=cfg,
            )
        )
        self.assertFalse(
            requires_detect_first_before_record(
                args=SimpleNamespace(input=None),
                app_config={"video.source": "file"},
            )
        )

    def test_motion_immediate_skips_go2rtc_probe(self):
        cfg = {
            "video.source": "go2rtc",
            "processor.detect_scheduler_enabled": True,
            "processor.detect_scheduler_triggers": ["opencv", "frigate"],
            "detection.track_first_gate_enabled": True,
        }
        self.assertFalse(
            should_run_probe(
                trigger_source="opencv",
                app_config=cfg,
                args=SimpleNamespace(input=None),
            )
        )


class TestTriggerRequiresDetectFirst(unittest.TestCase):
    def test_opencv_always_when_track_first_gate_in_detect_first_mode(self):
        cfg = {
            "video.source": "go2rtc",
            "processor.recording_gate_mode": RECORDING_GATE_DETECT_FIRST,
            "processor.detect_first_triggers": ["frigate"],
        }
        self.assertTrue(trigger_requires_detect_first(trigger_source="opencv", app_config=cfg))

    def test_respects_trigger_allowlist_in_detect_first_mode(self):
        cfg = {
            "video.source": "go2rtc",
            "processor.recording_gate_mode": RECORDING_GATE_DETECT_FIRST,
            "processor.detect_first_triggers": ["frigate"],
        }
        self.assertFalse(trigger_requires_detect_first(trigger_source="scales", app_config=cfg))

    def test_motion_immediate_never_requires_detect_first(self):
        cfg = {"video.source": "go2rtc", "processor.detect_first_triggers": ["opencv", "frigate"]}
        self.assertFalse(trigger_requires_detect_first(trigger_source="opencv", app_config=cfg))
        self.assertFalse(trigger_requires_detect_first(trigger_source="frigate", app_config=cfg))


if __name__ == "__main__":
    unittest.main()
