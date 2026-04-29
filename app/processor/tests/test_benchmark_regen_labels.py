"""Юнит-тесты для scripts/benchmark_regen_labels.py (#372)."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = next(
    (p for p in (Path(__file__).resolve().parents[3], Path('/workspace')) if (p / 'scripts').exists()),
    Path(__file__).resolve().parents[3],
)


def _load_benchmark_labels_module():
    path = _REPO_ROOT / 'scripts' / 'benchmark_regen_labels.py'
    spec = importlib.util.spec_from_file_location('benchmark_regen_labels', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['benchmark_regen_labels'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestBenchmarkRegenLabels(unittest.TestCase):
    """Загрузка gold JSON и сравнение с fused-треками."""

    @classmethod
    def setUpClass(cls):
        """Подгрузить модуль из repo ``scripts/``."""
        cls.mod = _load_benchmark_labels_module()

    def test_load_gold_by_basename(self):
        """Чтение JSON с ``gold_by_basename``."""
        payload = {
            'schema_version': 1,
            'gold_by_basename': {
                'a.mp4': ['Bird One', 'Bird Two'],
                'b.mp4': ['Single'],
            },
        }
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            encoding='utf-8',
        ) as f:
            json.dump(payload, f)
            p = f.name
        try:
            m = self.mod.load_gold_by_basename(p)
            self.assertEqual(m['a.mp4'], ['Bird One', 'Bird Two'])
            self.assertEqual(m['b.mp4'], ['Single'])
        finally:
            os.unlink(p)

    def test_eval_video_against_gold(self):
        """Missing/extra виды и recall."""
        fused = [
            {'species_name': 'Bird One'},
            {'species_name': 'Bird One'},
            {'species_name': 'Extra'},
        ]
        gm = {'x.mp4': ['Bird One', 'Bird Two']}
        ev = self.mod.eval_video_against_gold(gm, '/tmp/foo/x.mp4', fused)
        assert ev is not None
        self.assertEqual(ev['missing_vs_gold'], ['Bird Two'])
        self.assertEqual(ev['extra_vs_gold'], ['Extra'])
        self.assertAlmostEqual(ev['gold_species_recall'], 0.5)

    def test_eval_no_gold_returns_none(self):
        """Без строки в карте — ``None``."""
        ev = self.mod.eval_video_against_gold({}, '/tmp/nope.mp4', [])
        self.assertIsNone(ev)


if __name__ == '__main__':
    unittest.main()
