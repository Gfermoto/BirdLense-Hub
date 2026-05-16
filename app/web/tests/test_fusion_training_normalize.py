"""normalize_fusion_trace_row — колонки classifier uncertainty (#370)."""

from __future__ import annotations


def test_normalize_fusion_trace_row_classifier_uncertainty_columns():
    from services.fusion_training_service import normalize_fusion_trace_row

    full = normalize_fusion_trace_row(
        {
            "accepted": True,
            "track_id": 3,
            "video_id": 9,
            "classifier_entropy": 0.42,
            "classifier_top1_top2_margin": 0.07,
            "classifier_needs_review": True,
        },
    )
    assert full["classifier_entropy"] == 0.42
    assert full["classifier_top1_top2_margin"] == 0.07
    assert full["classifier_needs_review"] == 1

    empty = normalize_fusion_trace_row(
        {"accepted": False, "track_id": 0, "video_id": 0},
    )
    assert empty["classifier_entropy"] == ""
    assert empty["classifier_top1_top2_margin"] == ""
    assert empty["classifier_needs_review"] == 0
