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

        self.assertEqual(resolve_inference_backend(None), "torch")
        self.assertEqual(resolve_inference_backend({}), "torch")

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

    def test_assert_torch_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("torch")

    def test_assert_openvino_supported(self):
        from inference.selector import assert_backend_supported

        assert_backend_supported("openvino")

    def test_assert_planned_backend_raises(self):
        from inference.selector import assert_backend_supported

        with self.assertRaises(NotImplementedError):
            assert_backend_supported("onnxruntime")


if __name__ == "__main__":
    unittest.main()
