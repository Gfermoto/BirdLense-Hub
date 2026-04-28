"""Сравнение текущего smoke-отчёта с закоммиченным reference (#372)."""

import importlib.util
import json
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_compare():
    base = _REPO_ROOT / 'scripts' / 'compare_benchmark_reports.py'
    spec = importlib.util.spec_from_file_location(
        'compare_benchmark_reports',
        base,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['compare_benchmark_reports'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestReferenceSmokeCompare(unittest.TestCase):
    """Эталон reference_smoke_report.json vs синтетический current."""

    @classmethod
    def setUpClass(cls):
        """Загрузить compare_reports и эталонный JSON из репозитория."""
        cls.mod = _load_compare()
        ref_path = _REPO_ROOT / 'scripts' / 'ci' / 'reference_smoke_report.json'
        with open(ref_path, encoding='utf-8') as fh:
            cls.baseline = json.load(fh)

    def test_full_path_current_matches_baseline_basename(self):
        """Полный путь в current сопоставляется с baseline по basename."""
        current = {
            'report_format': 'benchmark_track_regen@v1',
            'videos': [
                {
                    'video': '/workspace/.artifacts/smoke_clip.mp4',
                    'raw_track_count': 1,
                    'fused_track_count': 0,
                },
            ],
        }
        ok, errs = self.mod.compare_reports(
            self.baseline,
            current,
            tolerance=0.0,
            match_by_basename=True,
        )
        self.assertTrue(ok, errs)


if __name__ == '__main__':
    unittest.main()
