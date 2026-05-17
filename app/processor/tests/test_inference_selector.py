"""Тесты выбора inference backend (#371)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestInferenceSelector(unittest.TestCase):
    def test_resolve_defaults_openvino(self):
        from inference.selector import resolve_inference_backend

        self.assertEqual(resolve_inference_backend(None), "openvino")
        self.assertEqual(resolve_inference_backend({}), "openvino")

    def test_resolve_env_overrides_config(self):
        from inference.selector import resolve_inference_backend

        old = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        try:
            os.environ["BIRDLENSE_INFERENCE_BACKEND"] = "TORCH"
            self.assertEqual(
                resolve_inference_backend({"processor.inference_backend": "ignored"}),
                "torch",
            )
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
            else:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old

    def test_resolve_from_config(self):
        from inference.selector import resolve_inference_backend

        old = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        try:
            self.assertEqual(
                resolve_inference_backend({"processor.inference_backend": "torch"}),
                "torch",
            )
        finally:
            if old is not None:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old

    def test_resolve_inference_device_defaults_none(self):
        from inference.selector import resolve_inference_device

        old = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            self.assertIsNone(resolve_inference_device(None))
            self.assertIsNone(resolve_inference_device({}))
            self.assertIsNone(resolve_inference_device({"processor.inference_device": ""}))
        finally:
            if old is not None:
                os.environ["BIRDLENSE_INFERENCE_DEVICE"] = old

    def test_resolve_inference_device_env(self):
        from inference.selector import resolve_inference_device

        old = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            os.environ["BIRDLENSE_INFERENCE_DEVICE"] = " intel:gpu "
            self.assertEqual(resolve_inference_device({"processor.inference_device": "cpu"}), "intel:gpu")
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
            else:
                os.environ["BIRDLENSE_INFERENCE_DEVICE"] = old

    def test_resolve_classifier_backend_defaults_torch(self):
        from inference.selector import resolve_classifier_inference_backend

        self.assertEqual(resolve_classifier_inference_backend(None), "torch")
        self.assertEqual(resolve_classifier_inference_backend({}), "torch")

    def test_resolve_classifier_device_defaults_from_detector_device(self):
        from inference.selector import resolve_classifier_inference_device

        old_cls = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", None)
        old_det = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            self.assertIsNone(resolve_classifier_inference_device(None))
            self.assertEqual(
                resolve_classifier_inference_device({"processor.inference_device": "intel:gpu"}),
                "intel:gpu",
            )
        finally:
            if old_cls is not None:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE"] = old_cls
            if old_det is not None:
                os.environ["BIRDLENSE_INFERENCE_DEVICE"] = old_det

    def test_resolve_classifier_device_env_overrides_detector(self):
        from inference.selector import resolve_classifier_inference_device

        old_cls = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", None)
        old_det = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE"] = "intel:gpu"
            os.environ["BIRDLENSE_INFERENCE_DEVICE"] = "intel:cpu"
            self.assertEqual(
                resolve_classifier_inference_device(
                    {
                        "processor.classifier_inference_device": "intel:npu",
                        "processor.inference_device": "intel:cpu",
                    }
                ),
                "intel:gpu",
            )
        finally:
            if old_cls is None:
                os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", None)
            else:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE"] = old_cls
            if old_det is None:
                os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
            else:
                os.environ["BIRDLENSE_INFERENCE_DEVICE"] = old_det

    def test_resolve_classifier_backend_env_overrides_config(self):
        from inference.selector import resolve_classifier_inference_backend

        old = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
        try:
            os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = "OPENVINO"
            self.assertEqual(
                resolve_classifier_inference_backend(
                    {"processor.classifier_inference_backend": "torch"},
                ),
                "openvino",
            )
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
            else:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old

    def test_assert_torch_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("torch")

    def test_assert_openvino_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("openvino")

    def test_assert_auto_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("auto")

    def test_assert_planned_backend_raises(self):
        from inference.selector import assert_backend_supported

        with self.assertRaises(NotImplementedError):
            assert_backend_supported("onnxruntime")

    def test_onnx_alias_resolves_to_onnxruntime(self):
        from inference.selector import assert_backend_supported, resolve_inference_backend

        old = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        try:
            os.environ["BIRDLENSE_INFERENCE_BACKEND"] = "onnx"
            self.assertEqual(resolve_inference_backend({}), "onnxruntime")
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
            else:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old
        with self.assertRaises(NotImplementedError):
            assert_backend_supported("onnx")

    def test_resolve_inference_device_env_overrides_config(self):
        from inference.selector import resolve_inference_device

        old = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            os.environ["BIRDLENSE_INFERENCE_DEVICE"] = "intel:gpu"
            self.assertEqual(
                resolve_inference_device({"processor.inference_device": "cpu"}),
                "intel:gpu",
            )
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
            else:
                os.environ["BIRDLENSE_INFERENCE_DEVICE"] = old

    def test_resolve_classifier_backend_independent_when_unset(self):
        from inference.selector import (
            resolve_classifier_inference_backend,
            resolve_inference_backend,
        )

        old = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
        try:
            cfg = {"processor.inference_backend": "openvino"}
            self.assertEqual(resolve_inference_backend(cfg), "openvino")
            self.assertEqual(resolve_classifier_inference_backend(cfg), "torch")
        finally:
            if old is not None:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old

    def test_resolve_classifier_backend_env_overrides(self):
        from inference.selector import resolve_classifier_inference_backend

        old = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
        try:
            os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = "openvino"
            self.assertEqual(
                resolve_classifier_inference_backend(
                    {"processor.classifier_inference_backend": "torch"},
                ),
                "openvino",
            )
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
            else:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old

    def test_resolve_classifier_device_defaults_to_main_device(self):
        from inference.selector import (
            resolve_classifier_inference_device,
            resolve_inference_device,
        )

        old = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", None)
        try:
            cfg = {"processor.inference_device": "intel:gpu"}
            self.assertEqual(resolve_inference_device(cfg), "intel:gpu")
            self.assertEqual(resolve_classifier_inference_device(cfg), "intel:gpu")
        finally:
            if old is not None:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE"] = old

    def test_openvino_device_policy_auto_prefers_gpu_then_cpu(self):
        from inference.selector import resolve_openvino_device_policy

        self.assertEqual(
            resolve_openvino_device_policy("auto"),
            ["intel:gpu", "intel:cpu"],
        )

    def test_openvino_device_policy_explicit_cpu(self):
        from inference.selector import resolve_openvino_device_policy

        self.assertEqual(resolve_openvino_device_policy("intel:cpu"), ["intel:cpu"])
        self.assertEqual(resolve_openvino_device_policy("cpu"), ["intel:cpu"])

    def test_resolve_openvino_profile_defaults_latency(self):
        from inference.selector import resolve_openvino_profile

        old = os.environ.pop("BIRDLENSE_OPENVINO_PROFILE", None)
        try:
            self.assertEqual(resolve_openvino_profile({}), "latency")
            self.assertEqual(
                resolve_openvino_profile({"processor.openvino.profile": "throughput"}),
                "throughput",
            )
        finally:
            if old is not None:
                os.environ["BIRDLENSE_OPENVINO_PROFILE"] = old

    def test_resolve_openvino_num_requests_env_override(self):
        from inference.selector import resolve_openvino_num_requests

        old = os.environ.pop("BIRDLENSE_OPENVINO_NUM_REQUESTS", None)
        try:
            os.environ["BIRDLENSE_OPENVINO_NUM_REQUESTS"] = "4"
            self.assertEqual(
                resolve_openvino_num_requests({"processor.openvino.num_requests": 1}),
                4,
            )
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_OPENVINO_NUM_REQUESTS", None)
            else:
                os.environ["BIRDLENSE_OPENVINO_NUM_REQUESTS"] = old


if __name__ == "__main__":
    unittest.main()
