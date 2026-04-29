"""Тесты inference.torch_backend (#371)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, "../src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


class TestTorchBackend(unittest.TestCase):
    def test_load_yolo_detector_onnxruntime_not_implemented(self):
        from inference.torch_backend import load_yolo_detector

        with self.assertRaises(NotImplementedError) as ctx:
            load_yolo_detector("dummy.onnx", backend="onnxruntime")
        self.assertIn("#371", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
