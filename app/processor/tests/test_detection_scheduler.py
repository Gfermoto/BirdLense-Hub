"""Detection scheduler trigger gating tests."""

import os
import sys
import unittest
from types import SimpleNamespace

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from detection_scheduler import (  # noqa: E402
    is_valid_detect_first_anchor,
    requires_detect_first_before_record,
    should_run_probe,
)


class TestDetectionScheduler(unittest.TestCase):
    def test_probe_enabled_for_configured_trigger(self):
        cfg = {
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
            "processor.detect_scheduler_enabled": True,
            "processor.detect_scheduler_triggers": ["opencv", "frigate", "scales"],
        }
        self.assertTrue(
            should_run_probe(trigger_source="opencv", app_config=cfg)
        )

    def test_probe_opencv_forced_when_track_first_and_legacy_triggers(self):
        """Legacy user_config without opencv still probes when track-first gate is on."""
        cfg = {
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
        self.assertFalse(is_valid_detect_first_anchor({"detect_first_bypassed": True}))
        self.assertFalse(is_valid_detect_first_anchor({"track_id": 1}))
        self.assertTrue(
            is_valid_detect_first_anchor({"track_id": 7, "bbox": [0.1, 0.2, 0.3, 0.4]})
        )

    def test_requires_detect_first_for_go2rtc_live(self):
        cfg = {"video.source": "go2rtc"}
        self.assertTrue(requires_detect_first_before_record(args=SimpleNamespace(input=None), app_config=cfg))
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


if __name__ == "__main__":
    unittest.main()
