"""Tests for inference bootstrap validation (#618)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestInferenceBootstrap(unittest.TestCase):
    def test_default_torch_plan(self):
        from inference_bootstrap import validate_inference_at_bootstrap

        old = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        try:
            plan = validate_inference_at_bootstrap({})
            self.assertEqual(plan.requested_backend, "torch")
            self.assertEqual(plan.effective_backend, "torch")
            self.assertFalse(plan.auto_torch_fallback)
        finally:
            if old is not None:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old

    def test_tensorrt_plan_when_engine_present(self):
        from inference_bootstrap import validate_inference_at_bootstrap

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            engine = os.path.join(
                proc, "models/detection/trapper_ai_v02_2024/trapper.engine"
            )
            os.makedirs(os.path.dirname(engine), exist_ok=True)
            with open(engine, "wb") as f:
                f.write(b"trt")
            plan = validate_inference_at_bootstrap(
                {
                    "processor.inference_backend": "tensorrt",
                    "processor.models.binary_tensorrt": (
                        "models/detection/trapper_ai_v02_2024/trapper.engine"
                    ),
                },
            )
        self.assertEqual(plan.effective_backend, "tensorrt")

    def test_record_metrics_sets_gauges(self):
        from inference_bootstrap import InferenceBootstrapPlan, record_inference_bootstrap_metrics
        from processor_runtime_stats import runtime_stats_snapshot

        record_inference_bootstrap_metrics(
            InferenceBootstrapPlan(
                requested_backend="torch",
                effective_backend="torch",
                auto_torch_fallback=False,
            ),
        )
        snap = runtime_stats_snapshot()
        self.assertEqual(snap.get("gauges", {}).get("inference_backend_effective"), "torch")


if __name__ == "__main__":
    unittest.main()
