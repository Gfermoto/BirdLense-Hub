"""Tests for classifier torch/ONNX weight path resolver."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

VARIANT = "convnext_v2_tiny_eu-common256px"


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

    def test_birder_default_torch_path(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            model_dir = os.path.join(proc, "models/classification", VARIANT)
            os.makedirs(model_dir, exist_ok=True)
            pt = os.path.join(model_dir, f"{VARIANT}.pt")
            with open(pt, "wb") as f:
                f.write(b"x")
            path, backend = resolve_classifier_weight_path(
                {"processor.classifier_inference_backend": "torch"},
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

    def test_birder_eu_onnx_path(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            model_dir = os.path.join(proc, "models/classification", VARIANT)
            os.makedirs(model_dir, exist_ok=True)
            onnx = os.path.join(model_dir, f"{VARIANT}.onnx")
            labels = os.path.join(model_dir, "class_labels.txt")
            with open(onnx, "wb") as f:
                f.write(b"x")
            with open(labels, "w", encoding="utf-8") as f:
                f.write("Eurasian jay\n")
            cfg = {
                "processor.classifier_engine": "birder_eu",
                "processor.classifier_inference_backend": "onnxruntime",
                "processor.models.classifier": (
                    f"models/classification/{VARIANT}/{VARIANT}.onnx"
                ),
            }
            with patch(
                "inference.selector.onnxruntime_classifier_available",
                return_value=True,
            ):
                path, backend = resolve_classifier_weight_path(cfg, proc)
            self.assertEqual(backend, "onnxruntime")
            self.assertTrue(path.endswith(VARIANT))

    def test_birder_eu_weights_classifier_path(self):
        from inference.classifier_paths import resolve_classifier_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            model_dir = os.path.join(proc, "models/classification", VARIANT)
            os.makedirs(model_dir, exist_ok=True)
            pt = os.path.join(model_dir, f"{VARIANT}.pt")
            with open(pt, "wb") as f:
                f.write(b"x")
            cfg = {
                "processor.classifier_engine": "birder_eu",
                "processor.classifier_inference_backend": "torch",
                "processor.models.classifier": (
                    f"models/classification/{VARIANT}/{VARIANT}.pt"
                ),
            }
            path, backend = resolve_classifier_weight_path(cfg, proc)
            self.assertEqual(backend, "torch")
            self.assertTrue(path.endswith(f"{VARIANT}.pt"))

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
