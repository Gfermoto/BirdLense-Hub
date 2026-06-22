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

    def test_ornimetrics_region_selects_nabirds_for_us_ca(self):
        from inference.classifier_paths import (
            resolve_classifier_weight_path,
            resolve_ornimetrics_species_pack,
        )

        cfg = {
            "processor.classifier_engine": "ornimetrics",
            "processor.classifier_inference_backend": "auto",
            "ebird.country": "CA",
        }
        with patch(
            "inference.selector.onnxruntime_classifier_available",
            return_value=True,
        ):
            path, backend = resolve_classifier_weight_path(cfg, "/tmp/processor")
        self.assertEqual(resolve_ornimetrics_species_pack(cfg), "nabirds")
        self.assertEqual(backend, "onnxruntime")
        self.assertTrue(
            path.endswith(
                "models/classification/ornimetrics/"
                "species_classifier_nabirds.onnx",
            ),
        )

    def test_ornimetrics_region_selects_inat_for_non_na(self):
        from inference.classifier_paths import (
            resolve_classifier_weight_path,
            resolve_ornimetrics_species_pack,
        )

        cfg = {
            "processor.classifier_engine": "ornimetrics",
            "processor.classifier_inference_backend": "auto",
            "ebird.country": "RU",
        }
        with patch(
            "inference.selector.onnxruntime_classifier_available",
            return_value=True,
        ):
            path, backend = resolve_classifier_weight_path(cfg, "/tmp/processor")
        self.assertEqual(resolve_ornimetrics_species_pack(cfg), "inat")
        self.assertEqual(backend, "onnxruntime")
        self.assertTrue(
            path.endswith(
                "models/classification/ornimetrics/"
                "species_classifier_inat.onnx",
            ),
        )

    def test_chriamue_explicit_classifier_path(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            weights = os.path.join(
                proc,
                "models/classification/chriamue_bird_species_classifier",
            )
            os.makedirs(weights, exist_ok=True)
            with open(os.path.join(weights, "model.onnx"), "wb") as f:
                f.write(b"x")
            cfg = {
                "processor.classifier_engine": "chriamue",
                "processor.classifier_inference_backend": "onnxruntime",
                "processor.models.classifier": (
                    "models/classification/chriamue_bird_species_classifier"
                ),
            }
            with patch(
                "inference.selector.onnxruntime_classifier_available",
                return_value=True,
            ):
                path, backend = resolve_classifier_weight_path(cfg, proc)
            self.assertEqual(backend, "onnxruntime")
            self.assertTrue(path.endswith("chriamue_bird_species_classifier"))

    def test_ornimetrics_pack_override_wins(self):
        from inference.classifier_paths import resolve_ornimetrics_species_pack

        self.assertEqual(
            resolve_ornimetrics_species_pack(
                {
                    "processor.ornimetrics_species_pack": "inat",
                    "ebird.country": "US",
                }
            ),
            "inat",
        )


if __name__ == "__main__":
    unittest.main()
