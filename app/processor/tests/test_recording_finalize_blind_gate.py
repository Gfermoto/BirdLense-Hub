"""Blind confirmation frigate gate (zero-frigate sessions)."""

from __future__ import annotations

from recording_finalize import _compute_blind_score


def _frigate_blind_gate(frigate_only_now: int, blind_min_frigate: int) -> bool:
    return blind_min_frigate <= 0 or frigate_only_now >= blind_min_frigate


def test_zero_frigate_threshold_allows_blind_without_frigate_extensions():
    assert _frigate_blind_gate(0, 0) is True
    assert _frigate_blind_gate(0, 120) is False
    assert _frigate_blind_gate(150, 120) is True


def test_blind_score_treats_zero_frigate_requirement_as_satisfied():
    score = _compute_blind_score(
        yolo_ran_now=200,
        yolo_raw_now=0,
        frigate_only_now=0,
        current_duration_s=60.0,
        required_frames=180,
        min_frigate_frames=0,
        min_duration_s=30.0,
    )
    assert score >= 0.55
