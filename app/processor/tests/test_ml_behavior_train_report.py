"""Synthetic tests for scripts/ml_behavior_train_report.py (Wave 2)."""

import importlib.util
import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = _REPO_ROOT / 'scripts' / 'ml_behavior_train_report.py'
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location('ml_behavior_train_report', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules['ml_behavior_train_report'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMlBehaviorTrainReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_report_metrics_and_gate_pass(self):
        manifest = {
            'schema': 'behavior_dataset_manifest@v1',
            'dataset_id': 'beh-003',
            'taxonomy': [
                {'id': 1, 'label': 'alert'},
                {'id': 2, 'label': 'feeding'},
            ],
            'videos': [
                {'video_key': 'v1', 'split': 'val', 'behavior_labels': ['alert']},
                {'video_key': 'v2', 'split': 'val', 'behavior_labels': ['feeding']},
            ],
        }
        predictions = {
            'predictions': [
                {'video_key': 'v1', 'pred_label': 'alert', 'confidence': 0.9},
                {'video_key': 'v2', 'pred_label': 'feeding', 'confidence': 0.85},
            ]
        }
        out = self.mod.build_behavior_train_report(
            manifest=manifest,
            predictions=predictions,
            split='val',
            min_macro_f1=0.5,
        )
        self.assertTrue(out['ok'])
        self.assertAlmostEqual(float(out['metrics']['accuracy']), 1.0, places=6)
        self.assertAlmostEqual(float(out['metrics']['macro_f1']), 1.0, places=6)
        self.assertTrue(out['gates']['macro_f1_ok'])

    def test_report_gate_fails_on_bad_predictions(self):
        manifest = {
            'schema': 'behavior_dataset_manifest@v1',
            'dataset_id': 'beh-004',
            'taxonomy': [
                {'id': 1, 'label': 'alert'},
                {'id': 2, 'label': 'feeding'},
            ],
            'videos': [
                {'video_key': 'v1', 'split': 'val', 'behavior_labels': ['alert']},
                {'video_key': 'v2', 'split': 'val', 'behavior_labels': ['feeding']},
            ],
        }
        predictions = {
            'predictions': [
                {'video_key': 'v1', 'pred_label': 'feeding', 'confidence': 0.9},
                {'video_key': 'v2', 'pred_label': 'alert', 'confidence': 0.85},
            ]
        }
        out = self.mod.build_behavior_train_report(
            manifest=manifest,
            predictions=predictions,
            split='val',
            min_macro_f1=0.5,
        )
        self.assertFalse(out['ok'])
        self.assertFalse(out['gates']['macro_f1_ok'])
        self.assertAlmostEqual(float(out['metrics']['accuracy']), 0.0, places=6)


if __name__ == '__main__':
    unittest.main()
