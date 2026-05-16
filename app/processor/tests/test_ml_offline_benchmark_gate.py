"""Synthetic tests for offline benchmark gate runner (#407)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'ml_offline_benchmark_gate.py'
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location('ml_offline_benchmark_gate', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['ml_offline_benchmark_gate'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlOfflineBenchmarkGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_gate_passes_for_non_regressing_candidate(self):
        baseline = {
            'report_format': 'benchmark_track_regen@v1',
            'videos': [
                {
                    'video': 'clip1.mp4',
                    'label_eval': {
                        'gold_species': ['Great Tit'],
                        'predicted_species_unique': ['Great Tit'],
                        'gold_species_recall': 1.0,
                    },
                    'yolo_silent_clip_rate': 0.1,
                }
            ],
        }
        candidate = {
            'report_format': 'benchmark_track_regen@v1',
            'videos': [
                {
                    'video': 'clip1.mp4',
                    'label_eval': {
                        'gold_species': ['Great Tit'],
                        'predicted_species_unique': ['Great Tit'],
                        'gold_species_recall': 1.0,
                    },
                    'yolo_silent_clip_rate': 0.08,
                }
            ],
        }
        continuity = {'schema': 'detector_continuity_report@v1', 'metrics': {'track_gate_ok': True, 'crop_gate_ok': True}}
        report = self.mod.build_offline_benchmark_gate_report(
            baseline_report=baseline,
            candidate_report=candidate,
            continuity_report=continuity,
            recall_tolerance=0.0,
            max_recall_drop=0.02,
            max_yolo_silent_clip_rate=0.2,
            require_label_eval_samples=1,
        )
        self.assertTrue(report['ok'])
        self.assertTrue(report['gates']['compare_reports_ok'])
        self.assertTrue(report['gates']['baseline_protocol_ok'])
        self.assertTrue(report['gates']['label_eval_sample_gate_ok'])

    def test_gate_fails_for_recall_regression(self):
        baseline = {
            'report_format': 'benchmark_track_regen@v1',
            'videos': [
                {
                    'video': 'clip1.mp4',
                    'label_eval': {
                        'gold_species': ['Great Tit'],
                        'predicted_species_unique': ['Great Tit'],
                        'gold_species_recall': 1.0,
                    },
                    'yolo_silent_clip_rate': 0.05,
                }
            ],
        }
        candidate = {
            'report_format': 'benchmark_track_regen@v1',
            'videos': [
                {
                    'video': 'clip1.mp4',
                    'label_eval': {
                        'gold_species': ['Great Tit'],
                        'predicted_species_unique': [],
                        'gold_species_recall': 0.0,
                    },
                    'yolo_silent_clip_rate': 0.05,
                }
            ],
        }
        report = self.mod.build_offline_benchmark_gate_report(
            baseline_report=baseline,
            candidate_report=candidate,
            continuity_report=None,
            recall_tolerance=0.0,
            max_recall_drop=0.02,
            max_yolo_silent_clip_rate=0.2,
            require_label_eval_samples=1,
        )
        self.assertFalse(report['ok'])
        self.assertFalse(report['gates']['compare_reports_ok'])
        self.assertTrue(any('recall_regression' in err for err in report['compare_report_errors']))


if __name__ == '__main__':
    unittest.main()
