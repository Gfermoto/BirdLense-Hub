"""Tests for classifier OpenVINO/torch weight path resolver."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestClassifierPaths(unittest.TestCase):
    """Classifier path resolution and availability checks."""

    def test_torch_default_path(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        path, backend = resolve_classifier_weight_path(
            {
                "processor.classifier_engine": "yolo",
                "processor.classifier_inference_backend": "torch",
            },
            "/tmp/processor",
        )
        self.assertEqual(backend, "torch")
        self.assertTrue(path.endswith("best.pt"))

    def test_openvino_empty_when_unconfigured(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        old = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
        try:
            os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = "openvino"
            path, backend = resolve_classifier_weight_path({}, "/tmp/processor")
            self.assertEqual(backend, "torch")
            self.assertTrue(path.endswith("best.pt"))
        finally:
            if old is None:
                os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
            else:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old

    def test_auto_prefers_openvino_when_available(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            ov = os.path.join(d, "openvino")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with patch("inference.selector.openvino_runtime_available", return_value=True):
                path, backend = resolve_classifier_weight_path(
                    {
                        "processor.classifier_inference_backend": "auto",
                        "processor.models.classifier_openvino": ov,
                    },
                    "/tmp/processor",
                )
        self.assertEqual(backend, "openvino")
        self.assertEqual(path, ov)

    def test_auto_falls_back_to_torch_when_openvino_runtime_missing(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        old_backend = os.environ.pop("BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND", None)
        old_ov_path = os.environ.pop("BIRDLENSE_CLASSIFIER_OPENVINO_PATH", None)
        try:
            with tempfile.TemporaryDirectory() as d:
                ov = os.path.join(d, "openvino")
                os.makedirs(ov, exist_ok=True)
                with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                    f.write("<net />")
                with patch("inference.selector.openvino_runtime_available", return_value=False):
                    path, backend = resolve_classifier_weight_path(
                        {
                            "processor.classifier_inference_backend": "auto",
                            "processor.models.classifier_openvino": ov,
                            "processor.models.classifier": "models/classification/weights/best.pt",
                        },
                        "/tmp/processor",
                    )
                self.assertEqual(backend, "torch")
                self.assertTrue(path.endswith("best.pt"))
        finally:
            if old_backend is not None:
                os.environ["BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND"] = old_backend
            if old_ov_path is not None:
                os.environ["BIRDLENSE_CLASSIFIER_OPENVINO_PATH"] = old_ov_path


if __name__ == "__main__":
    unittest.main()
