"""Synthetic tests for scripts/ml_shadow_rollout_report.py (#408)."""

import os
import sys
import unittest

_current_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_current_dir, '../../..'))
_scripts_path = os.path.join(_repo_root, 'scripts')
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


def _mk_window(*, matched: int, gold: int) -> dict:
    return {
        'schema': 'benchmark_track_regen@v1',
        'videos': [
            {
                'label_eval': {
                    'matched': matched,
                    'gold_count': gold,
                }
            }
        ],
    }


class TestMlShadowRolloutReport(unittest.TestCase):
    """Shadow rollout gate behavior."""

    def test_canary_ready_with_two_good_windows(self):
        """Returns canary_ready when two windows pass gates."""
        from ml_shadow_rollout_report import build_shadow_rollout_report

        out = build_shadow_rollout_report(
            window_reports=[
                _mk_window(matched=95, gold=100),
                _mk_window(matched=96, gold=100),
            ],
            critical_incidents=0,
            max_disagreement_rate=0.06,
            min_windows=2,
        )
        self.assertTrue(out['ok'])
        self.assertEqual(out['gate_verdict'], 'canary_ready')

    def test_hold_when_incident_present(self):
        """Returns hold when critical incident exists."""
        from ml_shadow_rollout_report import build_shadow_rollout_report

        out = build_shadow_rollout_report(
            window_reports=[
                _mk_window(matched=98, gold=100),
                _mk_window(matched=97, gold=100),
            ],
            critical_incidents=1,
            max_disagreement_rate=0.10,
            min_windows=2,
        )
        self.assertFalse(out['ok'])
        self.assertFalse(out['gates']['critical_incidents_ok'])


if __name__ == '__main__':
    unittest.main()
