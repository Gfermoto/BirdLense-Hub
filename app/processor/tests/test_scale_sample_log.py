"""Тесты журнала весов и оценки дельты за окно (#167)."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '../src'))
sys.path.insert(0, src_path)

from scale_sample_log import append_feeder_scale_sample, estimate_weight_delta_kg


def test_estimate_delta_requires_min_samples(tmp_path):
    d = str(tmp_path)
    t0 = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=30)
    path = tmp_path / "feeder_scale_history.jsonl"
    path.write_text(
        json.dumps({"t": t0.isoformat(), "weight": 1.0, "unit": "kg"}) + "\n",
        encoding="utf-8",
    )
    est, n = estimate_weight_delta_kg(d, t0, t1, min_delta_kg=0.001)
    assert est is None
    assert n == 1


def test_estimate_delta_max_min(tmp_path):
    d = str(tmp_path)
    t0 = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    mid = t0 + timedelta(seconds=5)
    t1 = t0 + timedelta(seconds=30)
    path = tmp_path / "feeder_scale_history.jsonl"
    path.write_text(
        json.dumps({"t": t0.isoformat(), "weight": 1.0, "unit": "kg"})
        + "\n"
        + json.dumps({"t": mid.isoformat(), "weight": 1.05, "unit": "kg"})
        + "\n"
        + json.dumps({"t": t1.isoformat(), "weight": 1.02, "unit": "kg"})
        + "\n",
        encoding="utf-8",
    )
    est, n = estimate_weight_delta_kg(d, t0, t1, min_delta_kg=0.01)
    assert n == 3
    assert est is not None
    assert abs(est - 0.05) < 1e-6


def test_g_to_kg_in_estimate(tmp_path):
    d = str(tmp_path)
    t0 = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=10)
    path = tmp_path / "feeder_scale_history.jsonl"
    path.write_text(
        json.dumps({"t": t0.isoformat(), "weight": 1000, "unit": "g"})
        + "\n"
        + json.dumps({"t": t0.isoformat(), "weight": 1050, "unit": "g"})
        + "\n",
        encoding="utf-8",
    )
    est, n = estimate_weight_delta_kg(d, t0, t1, min_delta_kg=0.001)
    assert n == 2
    assert abs(est - 0.05) < 1e-9
