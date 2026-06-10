"""Tests for bbox/crop SLO gate (#642)."""

from __future__ import annotations

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, "../src"))
sys.path.insert(0, src_path)

from bbox_slo import bbox_layers_allowed, evaluate_bbox_slo_ok  # noqa: E402


class TestBboxSloGate(unittest.TestCase):
    def test_disabled_always_ok(self):
        ok, reason = evaluate_bbox_slo_ok({"readiness.bbox_slo_gate_enabled": False})
        self.assertTrue(ok)
        self.assertEqual(reason, "gate_disabled")

    def test_env_force_red(self):
        os.environ["BIRDLENSE_BBOX_SLO_OK"] = "0"
        try:
            ok, reason = evaluate_bbox_slo_ok({})
            self.assertFalse(ok)
            self.assertEqual(reason, "env_force_red")
        finally:
            os.environ.pop("BIRDLENSE_BBOX_SLO_OK", None)

    def test_low_iou_red(self):
        hb = {"runtime_stats": {"gauges": {"bbox_parity_roundtrip_iou_p50": 0.30}}}
        ok, reason = evaluate_bbox_slo_ok(
            {"readiness.bbox_slo_min_iou_p50": 0.45},
            heartbeat_data=hb,
        )
        self.assertFalse(ok)
        self.assertIn("bbox_iou_p50", reason)

    def test_green_iou_ok(self):
        hb = {"bbox_parity_roundtrip_iou_p50": 0.55}
        ok, _ = evaluate_bbox_slo_ok({}, heartbeat_data=hb)
        self.assertTrue(ok)

    def test_funnel_degraded_red(self):
        ok, reason = evaluate_bbox_slo_ok(
            {"readiness.bbox_slo_allow_unknown_metrics": False},
            funnel_status="degraded",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "funnel_degraded")

    def test_bbox_layers_allowed_logs_red(self):
        self.assertFalse(
            bbox_layers_allowed(
                {},
                heartbeat_data={"bbox_parity_roundtrip_iou_p50": 0.1},
            )
        )


if __name__ == "__main__":
    unittest.main()
