"""Tests for inference bootstrap validation (#618)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestInferenceBootstrap(unittest.TestCase):
    def test_openvino_strict_missing_path_raises(self):
        from inference_bootstrap import validate_inference_at_bootstrap

        old = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        try:
            os.environ["BIRDLENSE_INFERENCE_BACKEND"] = "openvino"
            with self.assertRaises(FileNotFoundError):
                validate_inference_at_bootstrap(
                    {
                        "processor.inference_backend": "openvino",
                        "processor.openvino_binary_enabled": True,
                    },
                )
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
            else:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old

    def test_openvino_strict_incomplete_ir_raises(self):
        from inference_bootstrap import validate_inference_at_bootstrap

        with tempfile.TemporaryDirectory() as d:
            ov = os.path.join(d, "broken_openvino")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            old = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
            try:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = "openvino"
                with patch("inference.selector.openvino_runtime_available", return_value=True):
                    with self.assertRaises(FileNotFoundError):
                        validate_inference_at_bootstrap(
                            {
                                "processor.inference_backend": "openvino",
                                "processor.openvino_binary_enabled": True,
                                "processor.models.binary_openvino": ov,
                            },
                        )
            finally:
                if old is None:
                    os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
                else:
                    os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old

    def test_auto_invalid_ir_plans_torch_fallback(self):
        from inference_bootstrap import validate_inference_at_bootstrap

        with tempfile.TemporaryDirectory() as d:
            ov = os.path.join(d, "broken_openvino")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with patch("inference.selector.openvino_runtime_available", return_value=True):
                plan = validate_inference_at_bootstrap(
                    {
                        "processor.inference_backend": "auto",
                        "processor.openvino_binary_enabled": True,
                        "processor.models.binary_openvino": ov,
                    },
                )
        self.assertEqual(plan.requested_backend, "auto")
        self.assertEqual(plan.effective_backend, "torch")
        self.assertTrue(plan.auto_torch_fallback)
        self.assertEqual(plan.auto_torch_fallback_reason, "invalid_openvino_ir")

    def test_auto_valid_ir_plans_openvino(self):
        from inference_bootstrap import validate_inference_at_bootstrap

        with tempfile.TemporaryDirectory() as d:
            ov = os.path.join(d, "openvino")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with open(os.path.join(ov, "best.bin"), "wb") as f:
                f.write(b"\x00")
            with patch("inference.selector.openvino_runtime_available", return_value=True):
                plan = validate_inference_at_bootstrap(
                    {
                        "processor.inference_backend": "auto",
                        "processor.openvino_binary_enabled": True,
                        "processor.models.binary_openvino": ov,
                    },
                )
        self.assertEqual(plan.effective_backend, "openvino")
        self.assertFalse(plan.auto_torch_fallback)

    def test_record_metrics_increments_auto_fallback_counter(self):
        from inference_bootstrap import InferenceBootstrapPlan, record_inference_bootstrap_metrics
        from processor_runtime_stats import runtime_stats_snapshot

        record_inference_bootstrap_metrics(
            InferenceBootstrapPlan(
                requested_backend="auto",
                effective_backend="torch",
                openvino_path="/tmp/missing",
                auto_torch_fallback=True,
                auto_torch_fallback_reason="invalid_openvino_ir",
            ),
        )
        snap = runtime_stats_snapshot()
        self.assertGreaterEqual(
            int(snap.get("counters", {}).get("inference_openvino_auto_torch_fallback_total") or 0),
            1,
        )
        self.assertEqual(snap.get("gauges", {}).get("inference_backend_effective"), "torch")


if __name__ == "__main__":
    unittest.main()
