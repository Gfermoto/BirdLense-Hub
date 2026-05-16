"""Tests for scripts/verify_benchmark_slice_gates.py (#391)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = next(
    (
        p
        for p in (Path(__file__).resolve().parents[3], Path('/workspace'))
        if (p / 'scripts').exists()
    ),
    Path(__file__).resolve().parents[3],
)


def _load_module():
    """Load slice gate verifier module from scripts directory."""
    path = _REPO_ROOT / 'scripts' / 'verify_benchmark_slice_gates.py'
    spec = importlib.util.spec_from_file_location(
        'verify_benchmark_slice_gates',
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['verify_benchmark_slice_gates'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestVerifyBenchmarkSliceGates(unittest.TestCase):
    """Validate per-slice benchmark gating logic."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_slice_gate_pass(self):
        """Slice gate passes when recall meets threshold."""
        report = {
            'videos': [
                {
                    'video': '/x/a.mp4',
                    'label_eval': {
                        'gold_species': ['A', 'B'],
                        'predicted_species_unique': ['A', 'B'],
                    },
                },
            ],
        }
        slice_map = {
            'a.mp4': {
                'season': 'spring',
                'camera': 'cam1',
                'domain': 'feeder',
            },
        }
        ok, summary = self.mod.verify_slices(
            report,
            slice_map=slice_map,
            group_by=['season', 'camera', 'domain'],
            min_gold_samples=1,
            min_recall=0.8,
        )
        self.assertTrue(ok, summary)
        self.assertEqual(summary['errors'], [])

    def test_slice_gate_fails_on_low_recall(self):
        """Slice gate fails when recall is below threshold."""
        report = {
            'videos': [
                {
                    'video': '/x/a.mp4',
                    'label_eval': {
                        'gold_species': ['A', 'B'],
                        'predicted_species_unique': ['A'],
                    },
                },
            ],
        }
        slice_map = {
            'a.mp4': {
                'season': 'winter',
                'camera': 'cam9',
                'domain': 'tree',
            },
        }
        ok, summary = self.mod.verify_slices(
            report,
            slice_map=slice_map,
            group_by=['season', 'camera', 'domain'],
            min_gold_samples=1,
            min_recall=0.8,
        )
        self.assertFalse(ok)
        self.assertTrue(any('slice_recall_below_threshold' in e for e in summary['errors']))


if __name__ == '__main__':
    unittest.main()
