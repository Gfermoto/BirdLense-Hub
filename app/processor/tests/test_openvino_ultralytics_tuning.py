"""Tests for OpenVINO Ultralytics tuning (#644)."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestBuildOpenvinoCompileConfig(unittest.TestCase):
    def test_latency_default_single_stream(self):
        from inference.openvino_ultralytics_tuning import build_openvino_compile_config

        cfg = build_openvino_compile_config({"profile": "latency", "num_requests": 0})
        self.assertEqual(cfg["PERFORMANCE_HINT"], "LATENCY")
        self.assertEqual(cfg["NUM_STREAMS"], "1")

    def test_throughput_with_num_requests(self):
        from inference.openvino_ultralytics_tuning import build_openvino_compile_config

        cfg = build_openvino_compile_config({"profile": "throughput", "num_requests": 4})
        self.assertEqual(cfg["PERFORMANCE_HINT"], "THROUGHPUT")
        self.assertEqual(cfg["NUM_STREAMS"], "4")

    def test_resolve_device_names(self):
        from inference.openvino_ultralytics_tuning import resolve_ultralytics_openvino_device_name

        self.assertEqual(resolve_ultralytics_openvino_device_name("intel:gpu"), "GPU")
        self.assertEqual(resolve_ultralytics_openvino_device_name("intel:cpu"), "CPU")


class TestClassifierAsyncSafe(unittest.TestCase):
    def test_disabled_by_config(self):
        from inference.openvino_ultralytics_tuning import classifier_async_safe_on_openvino_igpu

        self.assertFalse(
            classifier_async_safe_on_openvino_igpu(
                {"processor.classifier_async_enabled": False},
                classifier_backend="openvino",
                classifier_device="intel:gpu",
            ),
        )

    def test_openvino_igpu_enabled(self):
        from inference.openvino_ultralytics_tuning import classifier_async_safe_on_openvino_igpu

        self.assertTrue(
            classifier_async_safe_on_openvino_igpu(
                {"processor.classifier_async_enabled": True},
                classifier_backend="openvino",
                classifier_device="intel:gpu",
            ),
        )


class TestApplyOpenvinoUltralyticsTuning(unittest.TestCase):
    def test_skips_when_no_backend(self):
        from inference.openvino_ultralytics_tuning import apply_openvino_ultralytics_tuning

        class FakeYolo:
            model = None
            predictor = None

            def predict(self, *_args, **_kwargs):
                return []

        self.assertFalse(
            apply_openvino_ultralytics_tuning(
                FakeYolo(),
                device="intel:gpu",
                app_config={"processor.openvino.profile": "latency", "processor.openvino.num_requests": 0},
            ),
        )

    def test_recompile_injects_compiled_model(self):
        from inference.openvino_ultralytics_tuning import apply_openvino_ultralytics_tuning

        class AutoBack:
            pass

        autoback = AutoBack()
        autoback.ov_model = object()
        autoback.ov_compiled_model = object()
        autoback.device = "intel:gpu"
        autoback.inference_mode = ""

        class FakeYolo:
            def __init__(self):
                self.model = autoback
                self.predictor = None

        compiled = object()
        fake_ov = MagicMock()
        fake_ov.Core.return_value.compile_model.return_value = compiled
        with patch.dict(sys.modules, {"openvino": fake_ov}):
            ok = apply_openvino_ultralytics_tuning(
                FakeYolo(),
                device="intel:gpu",
                app_config={"processor.openvino.profile": "latency", "processor.openvino.num_requests": 1},
            )
        self.assertTrue(ok)
        self.assertIs(autoback.ov_compiled_model, compiled)
        self.assertEqual(autoback.inference_mode, "LATENCY")


if __name__ == "__main__":
    unittest.main()
