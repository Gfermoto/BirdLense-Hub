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

    def test_collect_metric_values_from_nested_path(self):
        """Сбор значений для PSI из videos[*].field и nested paths."""
        report = {
            'videos': [
                {'video': 'a.mp4', 'confidence_hist': [0.1, 0.2]},
                {'video': 'b.mp4', 'label_eval': {'entropy': 0.7}},
            ],
        }
        self.assertEqual(
            self.mod.collect_metric_values(report, 'confidence_hist'),
            [0.1, 0.2],
        )
        self.assertEqual(
            self.mod.collect_metric_values(report, 'label_eval.entropy'),
            [0.7],
        )

    def test_psi_drift_can_fail(self):
        """PSI drift gate ловит сдвиг распределения."""
        base = {
            'videos': [
                {'video': 'a.mp4', 'classifier_entropy_values': [0.1, 0.1, 0.2, 0.2]},
            ],
        }
        cur = {
            'videos': [
                {'video': 'a.mp4', 'classifier_entropy_values': [0.8, 0.8, 0.9, 0.9]},
            ],
        }
        ok, errs = self.mod.compare_reports(
            base,
            cur,
            tolerance=0.0,
            match_by_basename=False,
            psi_fields=['classifier_entropy_values'],
            psi_threshold=0.1,
        )
        self.assertFalse(ok)
        self.assertTrue(any('psi_drift' in e for e in errs))

    def test_species_recall_deltas(self):
        """Пер-видовые дельты recall считаются по gold/predicted."""
        base = {
            'videos': [
                {
                    'video': '/tmp/a.mp4',
                    'label_eval': {
                        'gold_species': ['Great Tit', 'Robin'],
                        'predicted_species_unique': ['Great Tit'],
                    },
                },
            ],
        }
        cur = {
            'videos': [
                {
                    'video': '/tmp/a.mp4',
                    'label_eval': {
                        'gold_species': ['Great Tit', 'Robin'],
                        'predicted_species_unique': ['Great Tit', 'Robin'],
                    },
                },
            ],
        }
        rows = self.mod.species_recall_deltas(base, cur, match_by_basename=False)
        by_species = {r['species']: r for r in rows}
        self.assertAlmostEqual(by_species['Great Tit']['delta_recall'], 0.0)
        self.assertAlmostEqual(by_species['Robin']['delta_recall'], 1.0)
