"""Tests for behavior_baseline_runtime (#416)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture()
def tiny_export(tmp_path: Path) -> Path:
    """Two-class logistic with 3 features (matches manifest_meta_v1)."""
    export = {
        "schema": "behavior_logistic_export@v1",
        "feature_mode": "manifest_meta_v1",
        "labels": ["feeding", "flying"],
        "coef": [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
        "intercept": [0.0, 0.1],
    }
    p = tmp_path / "beh.json"
    p.write_text(json.dumps(export), encoding="utf-8")
    return p


def test_predict_prefers_feeding_when_log_frames_high(tiny_export: Path):
    from behavior_baseline_runtime import BehaviorBaselineRuntime

    rt = BehaviorBaselineRuntime()
    assert rt.load_if_needed(str(tiny_export), processor_cwd=None)
    dets = [{"species_name": "Tit", "frames": [{"t": 0}] * 50}]
    label, conf = rt.predict_video(dets, duration_s=10.0)
    assert label == "feeding"
    assert conf > 0.5


def test_manifest_meta_features_matches_training_script():
    from behavior_baseline_runtime import manifest_row_meta_features

    row = {"frame_rows": 10, "subject_count": 4, "species_names": ["A", "B"]}
    v = manifest_row_meta_features(row)
    assert len(v) == 3
    assert v[0] == pytest.approx(np.log1p(10.0))
