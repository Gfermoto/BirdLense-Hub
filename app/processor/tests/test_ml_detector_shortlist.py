"""Synthetic tests for detector shortlist report builder (#405)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'ml_detector_shortlist.py'
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location('ml_detector_shortlist', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['ml_detector_shortlist'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlDetectorShortlist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_shortlist_excludes_blocked_license_candidates(self):
        continuity = {'schema': 'detector_continuity_report@v1', 'ok': True, 'metrics': {'track_gate_ok': True, 'crop_gate_ok': True}, 'rows': {'video_rows_total': 100, 'provider_counts': {'frigate': 30, 'yolo': 70}}}
        offline = {'schema': 'offline_benchmark_gate@v1', 'ok': True}
        report = self.mod.build_detector_shortlist_report(
            continuity_report=continuity,
            offline_gate_report=offline,
            shortlist_size=3,
        )
        blocked = set(report['compliance_verdict']['blocked_candidates'])
        shortlist_ids = {row['id'] for row in report['shortlist']}
        self.assertIn('birds-classification-yolov9', blocked)
        self.assertNotIn('birds-classification-yolov9', shortlist_ids)

    def test_bird_only_verdict_requires_continuity(self):
        continuity = {'schema': 'detector_continuity_report@v1', 'ok': False, 'metrics': {'track_gate_ok': False, 'crop_gate_ok': False}, 'rows': {'video_rows_total': 10, 'provider_counts': {'frigate': 2}}}
        report = self.mod.build_detector_shortlist_report(
            continuity_report=continuity,
            offline_gate_report=None,
            shortlist_size=2,
        )
        verdict = report['bird_only_verdict']
        self.assertEqual(verdict['status'], 'not_viable')
        self.assertTrue(verdict['requires_follow_up'])


if __name__ == '__main__':
    unittest.main()
