"""Synthetic tests for scripts/ml_full_rollout_watch_report.py (#410)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, '../../..'))
_scripts_path = os.path.join(_repo_root, 'scripts')
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


class TestMlFullRolloutWatchReport(unittest.TestCase):
    """72h watch report go/no-go checks."""

    def test_go_when_watch_windows_stable(self):
        """Returns go with healthy three-day watch windows."""
        from ml_full_rollout_watch_report import build_full_rollout_watch_report

        out = build_full_rollout_watch_report(
            before_report={
                'mean_recall_kpi': 0.90,
                'mean_runtime_seconds': 20.0,
            },
            after_report={
                'mean_recall_kpi': 0.905,
                'mean_runtime_seconds': 16.0,
            },
            watch_windows=[
                {
                    'window': 'd1',
                    'p95_latency_ms': 220,
                    'error_rate': 0.002,
                    'uptime_ratio': 0.999,
                },
                {
                    'window': 'd2',
                    'p95_latency_ms': 215,
                    'error_rate': 0.003,
                    'uptime_ratio': 0.998,
                },
                {
                    'window': 'd3',
                    'p95_latency_ms': 230,
                    'error_rate': 0.004,
                    'uptime_ratio': 0.999,
                },
            ],
            min_watch_hours=72,
            max_error_rate=0.01,
            max_p95_latency_ms=450,
        )
        self.assertTrue(out['ok'])
        self.assertEqual(out['go_no_go'], 'go')

    def test_no_go_when_watch_not_long_enough(self):
        """Returns no-go when watch duration is below 72h."""
        from ml_full_rollout_watch_report import build_full_rollout_watch_report

        out = build_full_rollout_watch_report(
            before_report={
                'mean_recall_kpi': 0.90,
                'mean_runtime_seconds': 20.0,
            },
            after_report={
                'mean_recall_kpi': 0.899,
                'mean_runtime_seconds': 18.0,
            },
            watch_windows=[
                {
                    'window': 'd1',
                    'p95_latency_ms': 220,
                    'error_rate': 0.002,
                    'uptime_ratio': 0.999,
                }
            ],
            min_watch_hours=72,
            max_error_rate=0.01,
            max_p95_latency_ms=450,
        )
        self.assertFalse(out['ok'])
        self.assertFalse(out['gates']['watch_window_count_ok'])


if __name__ == '__main__':
    unittest.main()
