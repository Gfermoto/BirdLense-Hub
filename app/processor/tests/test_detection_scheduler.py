"""Detection scheduler trigger gating tests."""

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.append(src_path)

from detection_scheduler import should_run_probe  # noqa: E402


class TestDetectionScheduler(unittest.TestCase):
    def test_probe_enabled_for_configured_trigger(self):
        cfg = {
            "processor.detect_scheduler_enabled": True,
            "processor.detect_scheduler_triggers": ["frigate", "scales"],
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

    def test_probe_disabled_globally(self):
        cfg = {"processor.detect_scheduler_enabled": False}
        self.assertFalse(
            should_run_probe(trigger_source="frigate", app_config=cfg)
        )


if __name__ == "__main__":
    unittest.main()
