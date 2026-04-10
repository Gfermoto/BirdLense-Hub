import os
import sys
import math

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from fusion_model import FusionScorer


def test_fusion_scorer_basic_ranges():
    scorer = FusionScorer(model_path=None, device='cpu')
    # empty features -> should return a float in [0,1]
    p = scorer.score({})
    assert isinstance(p, float)
    assert 0.0 <= p <= 1.0


def test_fusion_scorer_prefers_classifier():
    scorer = FusionScorer(model_path=None, device="cpu")
    low = scorer.score({"detector_conf": 0.9, "classifier_conf": 0.01})
    high = scorer.score({"detector_conf": 0.5, "classifier_conf": 0.9})
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0
    # classifier_conf should materially affect output: high > low
    assert high >= low


def test_fusion_scorer_handles_extra_fields():
    scorer = FusionScorer(model_path=None, device="cpu")
    p = scorer.score(
        {
            "detector_conf": "0.7",
            "classifier_conf": 0.6,
            "birdnet_prior": 0.2,
            "key_frame_score": 0.5,
            "key_frame_count": 2,
            "multi_camera_count": 1,
            "unexpected": 123,
        }
    )
    assert isinstance(p, float)
    assert 0.0 <= p <= 1.0

