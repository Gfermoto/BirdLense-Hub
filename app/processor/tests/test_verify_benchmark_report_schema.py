"""Тесты scripts/verify_benchmark_report_schema.py (#372)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'verify_benchmark_report_schema.py'
    spec = importlib.util.spec_from_file_location(
        'verify_benchmark_report_schema',
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['verify_benchmark_report_schema'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestVerifyBenchmarkReportSchema(unittest.TestCase):
    """Проверка структуры отчёта benchmark-track-regen."""

    @classmethod
    def setUpClass(cls):
        """Загрузка модуля из ``scripts/``."""
        cls.mod = _load_module()

    def test_valid_minimal(self):
        """Минимально корректный отчёт."""
        data = {
            'report_format': 'benchmark_track_regen@v1',
            'inference_backend': 'torch',
            'videos': [
                {
                    'video': '/x/a.mp4',
                    'raw_track_count': 0,
                    'fused_track_count': 0,
                },
            ],
        }
        ok, errs = self.mod.validate_report(data)
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_missing_videos(self):
        """Пустой videos — ошибка."""
        ok, errs = self.mod.validate_report({'videos': []})
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
