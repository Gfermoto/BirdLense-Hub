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


def test_estimate_slow_drift_rejected_when_spike_required(tmp_path):
    """Медленный дрейф: span может превысить порог, но ни один соседний шаг — нет."""
    d = str(tmp_path)
    t0 = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    path = tmp_path / "feeder_scale_history.jsonl"
    lines = []
    for i, w in enumerate([1.0, 1.002, 1.004, 1.006]):
        lines.append(
            json.dumps({
                "t": (t0 + timedelta(seconds=i)).isoformat(),
                "weight": w,
                "unit": "kg",
            })
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    est, n = estimate_weight_delta_kg(
        d, t0, t0 + timedelta(seconds=10), min_delta_kg=0.005, require_consecutive_spike=True
    )
    assert n == 4
    assert est is None


def test_estimate_drift_ok_when_spike_not_required(tmp_path):
    d = str(tmp_path)
    t0 = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    path = tmp_path / "feeder_scale_history.jsonl"
    lines = []
    for i, w in enumerate([1.0, 1.003, 1.006, 1.012]):
        lines.append(
            json.dumps({
                "t": (t0 + timedelta(seconds=i)).isoformat(),
                "weight": w,
                "unit": "kg",
            })
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    est, n = estimate_weight_delta_kg(
        d, t0, t0 + timedelta(seconds=10), min_delta_kg=0.008, require_consecutive_spike=False
    )
    assert n == 4
    assert est is not None
    assert abs(est - 0.012) < 1e-9


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


def test_estimate_reads_recent_tail_not_whole_file(tmp_path):
    """Old noise before the window must not be required; tail-read still finds the window."""
    d = str(tmp_path)
    t0 = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    path = tmp_path / "feeder_scale_history.jsonl"
    lines = []
    # Large stale prefix outside the window
    for i in range(500):
        lines.append(
            json.dumps(
                {
                    "t": (t0 - timedelta(hours=2, seconds=i)).isoformat(),
                    "weight": 0.5,
                    "unit": "kg",
                }
            )
        )
    mid = t0 + timedelta(seconds=2)
    t1 = t0 + timedelta(seconds=10)
    lines.append(json.dumps({"t": t0.isoformat(), "weight": 1.0, "unit": "kg"}))
    lines.append(json.dumps({"t": mid.isoformat(), "weight": 1.04, "unit": "kg"}))
    lines.append(json.dumps({"t": t1.isoformat(), "weight": 1.01, "unit": "kg"}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    est, n = estimate_weight_delta_kg(d, t0, t1, min_delta_kg=0.01)
    assert n == 3
    assert est is not None
    assert abs(est - 0.04) < 1e-6
