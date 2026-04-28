"""Тесты scripts/compare_benchmark_reports.py (#372)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_compare_module():
    path = _REPO_ROOT / 'scripts' / 'compare_benchmark_reports.py'
    spec = importlib.util.spec_from_file_location(
        'compare_benchmark_reports',
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['compare_benchmark_reports'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestCompareBenchmarkReports(unittest.TestCase):
    """Сравнение JSON отчётов benchmark-track-regen."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_compare_module()

    def test_recall_drop_fails(self):
        """Падение recall ниже baseline без tolerance — ошибка."""
        base = {
            'report_format': 'benchmark_track_regen@v1',
            'videos': [
                {
                    'video': '/tmp/a.mp4',
                    'label_eval': {'gold_species_recall': 0.9},
                },
            ],
        }
        cur = {
            'videos': [
                {
                    'video': '/tmp/a.mp4',
                    'label_eval': {'gold_species_recall': 0.5},
                },
            ],
        }
        ok, errs = self.mod.compare_reports(
            base, cur, tolerance=0.0, match_by_basename=False,
        )
        self.assertFalse(ok)
        self.assertTrue(any('recall_regression' in e for e in errs))

    def test_tolerance_allows_small_drop(self):
        """Допуск по tolerance пропускает небольшое падение."""
        base = {
            'videos': [
                {
                    'video': '/tmp/a.mp4',
                    'label_eval': {'gold_species_recall': 0.9},
                },
            ],
        }
        cur = {
            'videos': [
                {
                    'video': '/tmp/a.mp4',
                    'label_eval': {'gold_species_recall': 0.88},
                },
            ],
        }
        ok, errs = self.mod.compare_reports(
            base, cur, tolerance=0.05, match_by_basename=False,
        )
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_match_by_basename(self):
        """Совпадение по basename при разных префиксах пути."""
        base = {
            'videos': [
                {
                    'video': '/old/path/clip.mp4',
                    'label_eval': {'gold_species_recall': 1.0},
                },
            ],
        }
        cur = {
            'videos': [
                {
                    'video': '/new/path/clip.mp4',
                    'label_eval': {'gold_species_recall': 1.0},
                },
            ],
        }
        ok, errs = self.mod.compare_reports(
            base, cur, tolerance=0.0, match_by_basename=True,
        )
        self.assertTrue(ok)
