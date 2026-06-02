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

    def test_yolo_requires_explicit_classifier_path(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with self.assertRaises(FileNotFoundError):
            resolve_classifier_weight_path(
                {
                    "processor.classifier_engine": "yolo",
                    "processor.classifier_inference_backend": "torch",
                },
                "/tmp/processor",
            )

    def test_birder_default_openvino_path(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            w = os.path.join(proc, "models/classification/weights")
            ov = os.path.join(w, "convnext_v2_tiny_eu-common256px_openvino_model")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "openvino_model.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with patch("inference.selector.openvino_runtime_available", return_value=True):
                path, backend = resolve_classifier_weight_path(
                    {"processor.classifier_inference_backend": "openvino"},
                    proc,
                )
            self.assertEqual(backend, "openvino")
            self.assertTrue(path.endswith("_openvino_model"))

    def test_auto_prefers_openvino_when_available(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            ov = os.path.join(proc, "models/classification/weights/convnext_v2_tiny_eu-common256px_openvino_model")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "openvino_model.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with patch("inference.selector.openvino_runtime_available", return_value=True):
                path, backend = resolve_classifier_weight_path(
                    {"processor.classifier_inference_backend": "auto"},
                    proc,
                )
            self.assertEqual(backend, "openvino")
            self.assertEqual(path, ov)

    def test_auto_falls_back_to_torch_when_openvino_runtime_missing(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            w = os.path.join(proc, "models/classification/weights")
            ov = os.path.join(w, "convnext_v2_tiny_eu-common256px_openvino_model")
            pt = os.path.join(w, "convnext_v2_tiny_eu-common256px.pt")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "openvino_model.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with open(pt, "wb") as f:
                f.write(b"x")
            with patch("inference.selector.openvino_runtime_available", return_value=False):
                path, backend = resolve_classifier_weight_path(
                    {"processor.classifier_inference_backend": "auto"},
                    proc,
                )
            self.assertEqual(backend, "torch")
            self.assertTrue(path.endswith(".pt"))


if __name__ == "__main__":
    unittest.main()
