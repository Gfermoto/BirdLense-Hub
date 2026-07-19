"""Linear pipeline must keep ScoringEngine on live while legacy static gates stay off."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, "../src"))

from detection_quality import DetectionQualityConfig  # noqa: E402


class TestDetectionQualityLinearScoring(unittest.TestCase):
    def test_linear_keeps_scoring_engine_by_default(self):
        cfg = {
            "processor.pipeline_mode": "linear",
            "processor.scoring_engine_enabled": True,
        }
        dqc = DetectionQualityConfig.from_runtime_cfg(cfg)
        self.assertTrue(dqc.scoring_engine_enabled)
        self.assertFalse(dqc.motion_global_static_reject)

    def test_linear_can_disable_live_scoring_explicitly(self):
        cfg = {
            "processor.pipeline_mode": "linear",
            "processor.scoring_engine_enabled": True,
            "processor.linear_live_scoring_engine_enabled": False,
        }
        dqc = DetectionQualityConfig.from_runtime_cfg(cfg)
        self.assertFalse(dqc.scoring_engine_enabled)

    def test_legacy_pipeline_forced_to_linear_gates(self):
        """legacy is forced linear (#621): motion-global veto stays off."""
        cfg = {
            "processor.pipeline_mode": "legacy",
            "processor.scoring_engine_enabled": True,
            "processor.linear_live_scoring_engine_enabled": True,
            "processor.motion_global_static_reject_enabled": True,
        }
        dqc = DetectionQualityConfig.from_runtime_cfg(cfg)
        self.assertTrue(dqc.scoring_engine_enabled)
        self.assertFalse(dqc.motion_global_static_reject)

    def test_dual_pipeline_coerced_to_linear_quality_gates(self):
        # RC3: dual is forced linear — legacy quality gates stay disabled.
        cfg = {
            "processor.pipeline_mode": "dual",
            "processor.scoring_engine_enabled": True,
            "processor.motion_global_static_reject_enabled": True,
        }
        dqc = DetectionQualityConfig.from_runtime_cfg(cfg)
        self.assertTrue(dqc.scoring_engine_enabled)
        self.assertFalse(dqc.motion_global_static_reject)


if __name__ == "__main__":
    unittest.main()
