"""Tests for scripts/verify_model_registry_entry.py (#393)."""

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
    """Load verifier module from scripts directory."""
    path = _REPO_ROOT / 'scripts' / 'verify_model_registry_entry.py'
    spec = importlib.util.spec_from_file_location(
        'verify_model_registry_entry',
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['verify_model_registry_entry'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestVerifyModelRegistryEntry(unittest.TestCase):
    """Validate gating logic for release train registry entries."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def _valid_entry(self):
        """Return a registry entry that satisfies strict gates."""
        return {
            'schema': 'birdlense_model_registry_entry@v1',
            'candidate': {'name': 'detector-1', 'stage': 'canary'},
            'references': {
                'validation_report': {'ok': True, 'sha256': 'abc'},
                'benchmark_report': {
                    'report_format': 'benchmark_track_regen@v1',
                    'video_count': 2,
                },
                'dataset_quality_report': {'ok': True, 'sha256': 'q1'},
                'hard_negatives_report': {'ok': True, 'sha256': 'h1'},
            },
            'artifacts': {
                'binary': {'exists': True, 'fingerprint_sha256_16': 'deadbeef'},
                'dataset_info': {
                    'schema': 'birdlense_dataset_export_v2',
                    'ready_for_train': True,
                    'strict_quality_ok': True,
                },
            },
        }

    def test_valid_entry_passes_strict_requirements(self):
        """Strict verification should pass for valid payload."""
        ok, errs = self.mod.verify(
            self._valid_entry(),
            min_stage='shadow',
            require_benchmark=True,
            require_dataset_ready=True,
            require_dataset_quality=True,
            require_hard_negatives=True,
        )
        self.assertTrue(ok, errs)
        self.assertEqual(errs, [])

    def test_fails_on_stage_regression(self):
        """Required stage floor should reject lower candidate stage."""
        entry = self._valid_entry()
        entry['candidate']['stage'] = 'offline'
        ok, errs = self.mod.verify(
            entry,
            min_stage='canary',
            require_benchmark=False,
            require_dataset_ready=False,
            require_dataset_quality=False,
            require_hard_negatives=False,
        )
        self.assertFalse(ok)
        self.assertTrue(any('stage_below_required' in e for e in errs))

    def test_fails_on_missing_benchmark_when_required(self):
        """Benchmark report is mandatory when benchmark gate is enabled."""
        entry = self._valid_entry()
        entry['references']['benchmark_report'] = None
        ok, errs = self.mod.verify(
            entry,
            min_stage='offline',
            require_benchmark=True,
            require_dataset_ready=False,
            require_dataset_quality=False,
            require_hard_negatives=False,
        )
        self.assertFalse(ok)
        self.assertIn('benchmark_report_required', errs)

    def test_fails_on_missing_dataset_quality_when_required(self):
        """Dataset quality report is mandatory when corresponding gate enabled."""
        entry = self._valid_entry()
        entry['references']['dataset_quality_report'] = None
        ok, errs = self.mod.verify(
            entry,
            min_stage='offline',
            require_benchmark=False,
            require_dataset_ready=False,
            require_dataset_quality=True,
            require_hard_negatives=False,
        )
        self.assertFalse(ok)
        self.assertIn('dataset_quality_report_required', errs)

    def test_fails_on_bad_hard_negatives_report(self):
        """Hard negatives gate must reject report with failed status."""
        entry = self._valid_entry()
        entry['references']['hard_negatives_report'] = {
            'ok': False,
            'sha256': 'h1',
        }
        ok, errs = self.mod.verify(
            entry,
            min_stage='offline',
            require_benchmark=False,
            require_dataset_ready=False,
            require_dataset_quality=False,
            require_hard_negatives=True,
        )
        self.assertFalse(ok)
        self.assertIn('hard_negatives_report_not_ok', errs)


if __name__ == '__main__':
    unittest.main()
