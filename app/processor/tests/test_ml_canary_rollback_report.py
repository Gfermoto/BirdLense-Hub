"""Synthetic tests for scripts/ml_canary_rollback_report.py (#409)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, '../../..'))
_scripts_path = os.path.join(_repo_root, 'scripts')
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestMlCanaryRollbackReport(unittest.TestCase):
    """Canary and rollback drill checks."""

    def test_ok_when_canary_and_rollback_pass(self):
        """Succeeds when canary and rollback SLI are healthy."""
        from ml_canary_rollback_report import build_canary_rollback_report

        out = build_canary_rollback_report(
            baseline_sli={'p95_latency_ms': 200, 'error_rate': 0.001},
            canary_sli={'p95_latency_ms': 210, 'error_rate': 0.004},
            rollback_sli={'p95_latency_ms': 202, 'error_rate': 0.002},
            max_latency_regression_ratio=0.10,
            max_error_rate=0.01,
        )
        self.assertTrue(out['ok'])
        self.assertTrue(out['rollback_drill_passed'])

    def test_fail_when_canary_error_too_high(self):
        """Fails when canary error rate breaches threshold."""
        from ml_canary_rollback_report import build_canary_rollback_report

        out = build_canary_rollback_report(
            baseline_sli={'p95_latency_ms': 200, 'error_rate': 0.001},
            canary_sli={'p95_latency_ms': 205, 'error_rate': 0.02},
            rollback_sli={'p95_latency_ms': 200, 'error_rate': 0.001},
            max_latency_regression_ratio=0.10,
            max_error_rate=0.01,
        )
        self.assertFalse(out['ok'])
        self.assertFalse(out['gates']['canary_error_ok'])


if __name__ == '__main__':
    unittest.main()
