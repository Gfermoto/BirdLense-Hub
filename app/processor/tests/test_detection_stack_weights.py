"""Проверка helper'ов для весов бинарника (Phase 2, #371)."""

import os
import sys
import tempfile
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_app_path = os.path.abspath(os.path.join(_current_dir, "..", ".."))
_src_path = os.path.abspath(os.path.join(_current_dir, "..", "src"))
for _p in (_app_path, _src_path):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestCtorKwargsRegression(unittest.TestCase):
    """Несовместимые kwargs конструкторов стека должны падать до загрузки весов.

    Исторический пример: ``for_track_regen`` в ``TwoStageStrategy.__init__`` —
    процессор в цикле рестартовал, хотя офлайн YOLO был рабочий.
    """

    def test_rejects_fake_two_stage_kwarg(self):
        from detection_strategy import TwoStageStrategy
        from shared.ctor_kwarg_guard import assert_ctor_kwargs

        bad_kw = {"binary_model_path": "a", "classifier_model_path": "b", "for_track_regen": True}
        with self.assertRaises(TypeError) as ctx:
            assert_ctor_kwargs(TwoStageStrategy.__init__, bad_kw, label="probe")
        self.assertIn("for_track_regen", str(ctx.exception))

    def test_full_two_stage_kwarg_contract_ok(self):
        from detection_strategy import TwoStageStrategy
        from shared.ctor_kwarg_guard import assert_ctor_kwargs

        ok_kw = {
            "binary_model_path": "/tmp/x.pt",
            "classifier_model_path": "/tmp/y.pt",
            "regional_species": None,
            "detector_scope": ["Bird"],
            "min_center_dist": 0.1,
            "min_box_size_px": 64,
            "blur_threshold": 100.0,
            "max_blur_checks": 3,
            "max_classifications_per_frame": 2,
            "classification_scheduler": "priority",
            "binary_imgsz": 640,
            "weight_contract_mode": "warn",
            "inference_backend": "torch",
            "classifier_inference_backend": "torch",
            "binary_inference_device": None,
            "classifier_inference_device": None,
        }
        assert_ctor_kwargs(TwoStageStrategy.__init__, ok_kw, label="ok")

    def test_skips_when_callable_has_var_keyword(self):
        from shared.ctor_kwarg_guard import assert_ctor_kwargs

        def sink(**kw):
            return kw

        assert_ctor_kwargs(sink, {"unexpected": True}, label="**)")  # must not raise


class TestDetectorWeightsAvailable(unittest.TestCase):
    """Тесты ``detector_weights_available``."""

    def test_pt_file(self):
        from inference.binary_paths import detector_weights_available

        with tempfile.NamedTemporaryFile(suffix='.pt', delete=False) as f:
            path = f.name
        try:
            self.assertTrue(detector_weights_available(path))
        finally:
            os.unlink(path)

    def test_openvino_dir_with_xml(self):
        from inference.binary_paths import detector_weights_available

        with tempfile.TemporaryDirectory() as d:
            xm = os.path.join(d, 'model.xml')
            with open(xm, 'w', encoding='utf-8') as f:
                f.write('<xml />')
            self.assertTrue(detector_weights_available(d))

    def test_openvino_xml_file(self):
        from inference.binary_paths import detector_weights_available

        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as f:
            path = f.name
        try:
            self.assertTrue(detector_weights_available(path))
        finally:
            os.unlink(path)

    def test_empty_dir_false(self):
        from inference.binary_paths import detector_weights_available

        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(detector_weights_available(d))


if __name__ == '__main__':
    unittest.main()
