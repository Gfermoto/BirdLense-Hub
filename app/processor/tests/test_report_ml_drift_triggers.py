"""Tests for scripts/report_ml_drift_triggers.py (#535)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_mod():
    path = _REPO_ROOT / "scripts" / "report_ml_drift_triggers.py"
    spec = importlib.util.spec_from_file_location(
        "report_ml_drift_triggers",
        path,
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["report_ml_drift_triggers"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_no_trigger_when_deltas_within_thresholds():
    mod = _load_mod()
    report = mod.evaluate_drift(
        baseline={
            "metrics": {
                "binary_positive_rate": 0.4,
                "mean_confidence": 0.8,
                "species_entropy": 1.3,
            },
            "thresholds": {
                "binary_positive_rate_abs_delta": 0.2,
                "mean_confidence_abs_delta": 0.2,
                "species_entropy_abs_delta": 0.2,
            },
            "min_observations": 2,
        },
        observations=[
            {
                "observed_at": "2026-05-31T00:00:00Z",
                "binary_positive_rate": 0.41,
                "mean_confidence": 0.79,
                "species_entropy": 1.31,
            },
            {
                "observed_at": "2026-05-31T00:05:00Z",
                "binary_positive_rate": 0.39,
                "mean_confidence": 0.81,
                "species_entropy": 1.29,
            },
        ],
        override_reason="",
    )
    assert report["ok"] is True
    assert report["trigger"]["retrain_required"] is False


def test_trigger_blocks_when_drift_exceeds_threshold_without_override():
    mod = _load_mod()
    report = mod.evaluate_drift(
        baseline={
            "metrics": {
                "binary_positive_rate": 0.4,
                "mean_confidence": 0.8,
                "species_entropy": 1.3,
            },
            "thresholds": {
                "binary_positive_rate_abs_delta": 0.05,
                "mean_confidence_abs_delta": 0.05,
                "species_entropy_abs_delta": 0.05,
            },
            "min_observations": 1,
        },
        observations=[
            {
                "observed_at": "2026-05-31T00:00:00Z",
                "binary_positive_rate": 0.7,
                "mean_confidence": 0.9,
                "species_entropy": 1.9,
            }
        ],
        override_reason="",
    )
    assert report["ok"] is False
    assert report["trigger"]["block_release"] is True
