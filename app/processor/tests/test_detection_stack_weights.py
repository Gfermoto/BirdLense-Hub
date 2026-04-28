"""Проверка helper'ов для весов бинарника (Phase 2, #371)."""

import os
import sys
import tempfile
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_path = os.path.abspath(os.path.join(_current_dir, '../src'))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


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
