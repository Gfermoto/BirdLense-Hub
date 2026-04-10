import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from fusion_metrics import evaluate_binary_scores, evaluate_by_slice


def test_evaluate_binary_scores_reports_calibration_metrics():
    rows = [
        {'score': 0.95, 'label': 1, 'audio_evidence': 'support'},
        {'score': 0.85, 'label': 1, 'audio_evidence': 'support'},
        {'score': 0.20, 'label': 0, 'audio_evidence': 'conflict'},
        {'score': 0.10, 'label': 0, 'audio_evidence': 'none'},
    ]

    report = evaluate_binary_scores(rows, thresholds=(0.8, 0.9))

    assert report['n'] == 4
    assert report['brier'] >= 0.0
    assert report['ece'] >= 0.0
    assert report['thresholds']['0.90']['coverage'] == 0.25
    assert report['thresholds']['0.90']['precision'] == 1.0


def test_evaluate_by_slice_groups_values():
    rows = [
        {'score': 0.9, 'label': 1, 'audio_evidence': 'support'},
        {'score': 0.2, 'label': 0, 'audio_evidence': 'conflict'},
    ]

    report = evaluate_by_slice(rows, slice_field='audio_evidence')

    assert set(report) == {'support', 'conflict'}
    assert report['support']['n'] == 1
    assert report['conflict']['n'] == 1

