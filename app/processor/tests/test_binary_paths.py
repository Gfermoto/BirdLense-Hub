"""Тесты ``inference.binary_paths`` (#371)."""

import os
import sys
import tempfile
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestBinaryPaths(unittest.TestCase):
    def test_default_torch_path(self):
        from inference.binary_paths import resolve_binary_detector_weight_path

        path, backend = resolve_binary_detector_weight_path({}, "/tmp/processor")
        self.assertEqual(backend, "torch")
        self.assertTrue(path.endswith("yolo11n.pt"))

    def test_tensorrt_resolves_engine_path(self):
        from inference.binary_paths import detector_weights_available, resolve_binary_detector_weight_path

        with tempfile.TemporaryDirectory() as d:
            proc = os.path.join(d, "processor")
            engine = os.path.join(proc, "models/detection/weights/yolo11n.engine")
            os.makedirs(os.path.dirname(engine), exist_ok=True)
            with open(engine, "wb") as f:
                f.write(b"trt")
            path, backend = resolve_binary_detector_weight_path(
                {
                    "processor.inference_backend": "tensorrt",
                    "processor.models.binary_tensorrt": "models/detection/weights/yolo11n.engine",
                },
                proc,
            )
            self.assertTrue(detector_weights_available(path))
        self.assertEqual(backend, "tensorrt")
        self.assertTrue(path.endswith("yolo11n.engine"))


if __name__ == "__main__":
    unittest.main()
