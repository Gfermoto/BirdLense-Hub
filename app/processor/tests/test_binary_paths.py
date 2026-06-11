"""Тесты ``inference.binary_paths`` (#371)."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, '../src'))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestBinaryPaths(unittest.TestCase):
    """Резолв путей и отпечаток OpenVINO."""

    def test_openvino_default_path(self):
        from inference.binary_paths import resolve_binary_detector_weight_path

        path, backend = resolve_binary_detector_weight_path({}, '/tmp/processor')
        self.assertEqual(backend, 'torch')
        self.assertTrue(path.endswith('yolo11n.pt'))

    def test_openvino_empty_when_unconfigured(self):
        from inference.binary_paths import resolve_binary_detector_weight_path

        old = os.environ.pop('BIRDLENSE_INFERENCE_BACKEND', None)
        try:
            os.environ['BIRDLENSE_INFERENCE_BACKEND'] = 'openvino'
            path, backend = resolve_binary_detector_weight_path({}, '/tmp/processor')
            self.assertEqual(backend, 'torch')
            self.assertTrue(path.endswith('yolo11n.pt'))
        finally:
            if old is None:
                os.environ.pop('BIRDLENSE_INFERENCE_BACKEND', None)
            else:
                os.environ['BIRDLENSE_INFERENCE_BACKEND'] = old

    def test_openvino_bundle_fingerprint_dir(self):
        from inference.binary_paths import openvino_bundle_fingerprint

        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(openvino_bundle_fingerprint(d))
            xm = os.path.join(d, 'm.xml')
            with open(xm, 'w', encoding='utf-8') as f:
                f.write('<net />')
            fp = openvino_bundle_fingerprint(d)
            self.assertIsNotNone(fp)
            self.assertEqual(len(fp), 64)

    def test_auto_prefers_openvino_when_available(self):
        from inference.binary_paths import resolve_binary_detector_weight_path

        with tempfile.TemporaryDirectory() as d:
            ov = os.path.join(d, "openvino")
            os.makedirs(ov, exist_ok=True)
            with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with open(os.path.join(ov, "best.bin"), "wb") as f:
                f.write(b"\x00")
            with patch("inference.selector.openvino_runtime_available", return_value=True):
                path, backend = resolve_binary_detector_weight_path(
                    {
                        "processor.inference_backend": "auto",
                        "processor.openvino_binary_enabled": True,
                        "processor.models.binary_openvino": ov,
                    },
                    "/tmp/processor",
                )
        self.assertEqual(backend, "openvino")
        self.assertEqual(path, ov)

    def test_openvino_disabled_forces_torch_despite_auto(self):
        from inference.binary_paths import resolve_binary_detector_weight_path

        old_backend = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        old_ov_path = os.environ.pop("BIRDLENSE_BINARY_OPENVINO_PATH", None)
        try:
            with tempfile.TemporaryDirectory() as d:
                ov = os.path.join(d, "openvino")
                os.makedirs(ov, exist_ok=True)
                with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                    f.write("<net />")
                with open(os.path.join(ov, "best.bin"), "wb") as f:
                    f.write(b"\x00")
                with patch("inference.selector.openvino_runtime_available", return_value=True):
                    path, backend = resolve_binary_detector_weight_path(
                        {
                            "processor.inference_backend": "auto",
                            "processor.openvino_binary_enabled": False,
                            "processor.models.binary_openvino": ov,
                            "processor.models.binary": "models/detection/weights/best.pt",
                        },
                        "/tmp/processor",
                    )
                self.assertEqual(backend, "torch")
                self.assertTrue(path.endswith("best.pt"))
        finally:
            if old_backend is not None:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old_backend
            if old_ov_path is not None:
                os.environ["BIRDLENSE_BINARY_OPENVINO_PATH"] = old_ov_path

    def test_auto_falls_back_to_torch_when_openvino_runtime_missing(self):
        from inference.binary_paths import resolve_binary_detector_weight_path

        old_backend = os.environ.pop("BIRDLENSE_INFERENCE_BACKEND", None)
        old_ov_path = os.environ.pop("BIRDLENSE_BINARY_OPENVINO_PATH", None)
        try:
            with tempfile.TemporaryDirectory() as d:
                ov = os.path.join(d, "openvino")
                os.makedirs(ov, exist_ok=True)
                with open(os.path.join(ov, "best.xml"), "w", encoding="utf-8") as f:
                    f.write("<net />")
                with open(os.path.join(ov, "best.bin"), "wb") as f:
                    f.write(b"\x00")
                with patch("inference.selector.openvino_runtime_available", return_value=False):
                    path, backend = resolve_binary_detector_weight_path(
                        {
                            "processor.inference_backend": "auto",
                            "processor.models.binary_openvino": ov,
                            "processor.models.binary": "models/detection/weights/best.pt",
                        },
                        "/tmp/processor",
                    )
                self.assertEqual(backend, "torch")
                self.assertTrue(path.endswith("best.pt"))
        finally:
            if old_backend is not None:
                os.environ["BIRDLENSE_INFERENCE_BACKEND"] = old_backend
            if old_ov_path is not None:
                os.environ["BIRDLENSE_BINARY_OPENVINO_PATH"] = old_ov_path

    def test_openvino_expected_input_size_from_metadata(self):
        from inference.binary_paths import openvino_expected_input_size

        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "best.xml"), "w", encoding="utf-8") as f:
                f.write("<net />")
            with open(os.path.join(d, "metadata.yaml"), "w", encoding="utf-8") as f:
                f.write("imgsz:\n- 960\n- 960\n")
            self.assertEqual(openvino_expected_input_size(d), 960)

    def test_openvino_expected_input_size_from_xml_shape(self):
        from inference.binary_paths import openvino_expected_input_size

        xml = """
<net>
  <input>
    <port id="0">
      <dim>1</dim><dim>3</dim><dim>640</dim><dim>640</dim>
    </port>
  </input>
</net>
""".strip()
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "best.xml"), "w", encoding="utf-8") as f:
                f.write(xml)
            self.assertEqual(openvino_expected_input_size(d), 640)

    def test_openvino_expected_input_size_resolves_relative_model_path(self):
        from inference.binary_paths import openvino_expected_input_size, processor_package_root

        rel = "models/detection/weights/trapper_ai_v02_2024_openvino_model"
        abs_path = os.path.join(processor_package_root(), rel)
        if not os.path.isdir(abs_path):
            self.skipTest("trapper openvino bundle missing")
        self.assertEqual(openvino_expected_input_size(rel), 704)


if __name__ == '__main__':
    unittest.main()
