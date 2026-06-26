"""Тесты выбора inference backend (#371)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestInferenceSelector(unittest.TestCase):
    def test_resolve_defaults_torch(self):
        from inference.selector import resolve_inference_backend

        old = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        try:
            self.assertEqual(resolve_inference_backend(None), "torch")
            self.assertEqual(resolve_inference_backend({}), "torch")
        finally:
            if old is not None:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old

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
            self.assertEqual(
                resolve_inference_backend({"processor.inference_backend": "onnxruntime"}),
                "onnxruntime",
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
            os.environ["BIRDLENSE_INFERENCE_DEVICE"] = " cuda:0 "
            self.assertEqual(resolve_inference_device({"processor.inference_device": "cpu"}), "cuda:0")
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
            else:
                os.environ["BIRDLENSE_INFERENCE_DEVICE"] = old

    def test_resolve_classifier_backend_defaults_torch(self):
        from inference.selector import resolve_classifier_inference_backend

        old = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
        try:
            self.assertEqual(resolve_classifier_inference_backend(None), "torch")
            self.assertEqual(resolve_classifier_inference_backend({}), "torch")
        finally:
            if old is not None:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old

    def test_resolve_classifier_device_defaults_from_detector_device(self):
        from inference.selector import resolve_classifier_inference_device

        old_cls = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", None)
        old_det = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            self.assertIsNone(resolve_classifier_inference_device(None))
            self.assertEqual(
                resolve_classifier_inference_device({"processor.inference_device": "cuda:0"}),
                "cuda:0",
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
            os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE"] = "cuda:0"
            os.environ["BIRDLENSE_INFERENCE_DEVICE"] = "cpu"
            self.assertEqual(
                resolve_classifier_inference_device(
                    {
                        "processor.classifier_inference_device": "cuda:1",
                        "processor.inference_device": "cpu",
                    }
                ),
                "cuda:0",
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
            os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = "ONNXRUNTIME"
            self.assertEqual(
                resolve_classifier_inference_backend(
                    {"processor.classifier_inference_backend": "torch"},
                ),
                "onnxruntime",
            )
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
            else:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old

    def test_assert_torch_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("torch")

    def test_assert_onnxruntime_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("onnxruntime")

    def test_assert_auto_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("auto")

    def test_assert_unsupported_backend_raises(self):
        from inference.selector import assert_backend_supported

        with self.assertRaises(NotImplementedError):
            assert_backend_supported("openvino")

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
        assert_backend_supported("onnxruntime")

    def test_resolve_inference_device_env_overrides_config(self):
        from inference.selector import resolve_inference_device

        old = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            os.environ["BIRDLENSE_INFERENCE_DEVICE"] = "cuda:0"
            self.assertEqual(
                resolve_inference_device({"processor.inference_device": "cpu"}),
                "cuda:0",
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
            cfg = {"processor.inference_backend": "onnxruntime"}
            self.assertEqual(resolve_inference_backend(cfg), "onnxruntime")
            self.assertEqual(resolve_classifier_inference_backend(cfg), "torch")
        finally:
            if old is not None:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old

    def test_resolve_classifier_backend_env_overrides(self):
        from inference.selector import resolve_classifier_inference_backend

        old = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
        try:
            os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = "onnxruntime"
            self.assertEqual(
                resolve_classifier_inference_backend(
                    {"processor.classifier_inference_backend": "torch"},
                ),
                "onnxruntime",
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

        old_cls = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE", None)
        old_det = os.environ.pop("BIRDLENSE_INFERENCE_DEVICE", None)
        try:
            cfg = {"processor.inference_device": "cuda:0"}
            self.assertEqual(resolve_inference_device(cfg), "cuda:0")
            self.assertEqual(resolve_classifier_inference_device(cfg), "cuda:0")
        finally:
            if old_cls is not None:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE"] = old_cls
            if old_det is not None:
                os.environ["BIRDLENSE_INFERENCE_DEVICE"] = old_det


if __name__ == "__main__":
    unittest.main()
