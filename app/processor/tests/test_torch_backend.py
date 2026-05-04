"""Тесты inference.torch_backend (#371)."""

import os
import sys
import types
import unittest
from unittest.mock import patch

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

    def test_load_yolo_classifier_openvino_uses_openvino_path(self):
        from inference.torch_backend import load_yolo_classifier

        fake_ultra = types.ModuleType("ultralytics")
        with (
            patch("inference.torch_backend._ensure_openvino_pkg") as ensure_ov,
            patch("inference.torch_backend._apply_openvino_runtime_tuning") as tune_ov,
            patch.dict(sys.modules, {"ultralytics": fake_ultra}),
            patch.object(fake_ultra, "YOLO", create=True) as yolo_cls,
        ):
            model = object()
            yolo_cls.return_value = model
            out = load_yolo_classifier(
                "classifier_openvino_model",
                backend="openvino",
                openvino_profile="throughput",
                openvino_num_requests=2,
                openvino_model_cache_enabled=True,
            )

        self.assertIs(out, model)
        ensure_ov.assert_called_once()
        tune_ov.assert_called_once_with(
            profile="throughput",
            num_requests=2,
            model_cache_enabled=True,
        )
        yolo_cls.assert_called_once_with("classifier_openvino_model", task="classify")


if __name__ == "__main__":
    unittest.main()
