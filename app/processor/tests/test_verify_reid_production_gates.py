"""Tests for scripts/verify_reid_production_gates.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = next(
    (
        p
        for p in (Path(__file__).resolve().parents[3], Path('/workspace'))
        if (p / 'scripts').exists()
    ),
    Path(__file__).resolve().parents[3],
)


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'verify_reid_production_gates.py'
    spec = importlib.util.spec_from_file_location(
        'verify_reid_production_gates',
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['verify_reid_production_gates'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestVerifyReidProductionGates(unittest.TestCase):
    """Validation tests for Re-ID production gate script."""

    @classmethod
    def setUpClass(cls):
        """Load target module once."""
        cls.mod = _load_module()

    def test_verify_reid_gates_ok(self):
        """Green path with valid summary and match payloads."""
        reid_summary = {
            'schema': 'reid_summary@v2',
            'available': True,
            'embedding_count': 7,
            'contract': {
                'status': 'ok',
                'missing_contract_rows': 0,
                'max_embedding_age_hours': 4.0,
            },
        }
        reid_match = {
            'schema': 'video_reid_match@v2',
            'available': True,
            'contract_ready': True,
            'matches': [
                {
                    'decision': 'suggest_same_individual',
                    'policy_decision': 'suggest_same_individual',
                    'similarity': 0.93,
                    'effective_threshold': 0.89,
                }
            ],
        }
        ok, out = self.mod.verify_reid_gates(
            reid_summary=reid_summary,
            reid_match=reid_match,
            min_embeddings=1,
            max_missing_contract_rows=0,
            require_contract_ok=True,
            max_stale_hours=12.0,
            min_suggestion_count=1,
        )
        self.assertTrue(ok)
        self.assertTrue(out['ok'])

    def test_verify_reid_gates_fail_when_contract_bad(self):
        """Fail path when contract and freshness are degraded."""
        reid_summary = {
            'schema': 'reid_summary@v2',
            'available': True,
            'embedding_count': 0,
            'contract': {
                'status': 'degraded',
                'missing_contract_rows': 3,
                'max_embedding_age_hours': 99.0,
            },
        }
        ok, out = self.mod.verify_reid_gates(
            reid_summary=reid_summary,
            reid_match=None,
            min_embeddings=1,
            max_missing_contract_rows=0,
            require_contract_ok=True,
            max_stale_hours=24.0,
            min_suggestion_count=0,
        )
        self.assertFalse(ok)
        self.assertFalse(out['ok'])
        self.assertTrue(out['errors'])

    def test_cli_main_ok(self):
        """CLI returns zero for valid fixture files."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            reid_summary = base / 'reid_summary.json'
            reid_match = base / 'reid_match.json'
            reid_summary.write_text(
                json.dumps(
                    {
                        'schema': 'reid_summary@v2',
                        'available': True,
                        'embedding_count': 2,
                        'contract': {
                            'status': 'ok',
                            'missing_contract_rows': 0,
                            'max_embedding_age_hours': 1.0,
                        },
                    }
                ),
                encoding='utf-8',
            )
            reid_match.write_text(
                json.dumps(
                    {
                        'schema': 'video_reid_match@v2',
                        'available': True,
                        'contract_ready': True,
                        'matches': [
                            {
                                'decision': 'suggest_same_individual',
                                'policy_decision': (
                                    'suggest_same_individual'
                                ),
                                'similarity': 0.91,
                                'effective_threshold': 0.88,
                            }
                        ],
                    }
                ),
                encoding='utf-8',
            )
            argv_prev = sys.argv
            try:
                sys.argv = [
                    'verify_reid_production_gates.py',
                    '--reid-summary',
                    str(reid_summary),
                    '--reid-match',
                    str(reid_match),
                    '--require-contract-ok',
                    '--min-suggestion-count',
                    '1',
                ]
                rc = self.mod.main()
            finally:
                sys.argv = argv_prev
            self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
