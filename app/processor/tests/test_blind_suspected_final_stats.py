"""Blind suspected must use final runtime_signals counters."""

from __future__ import annotations

from recording_finalize import _blind_suspected_from_final_stats


def test_suspected_false_when_final_raw_boxes():
    rs = {"yolo_raw_boxes_total": 2, "yolo_frames_with_tracks": 0, "yolo_frames_with_raw_boxes": 0}
    assert not _blind_suspected_from_final_stats(final_rs=rs, blind_score=0.9, blind_score_threshold=0.7)


def test_suspected_false_when_final_track_frames_only():
    rs = {"yolo_raw_boxes_total": 0, "yolo_frames_with_tracks": 1, "yolo_frames_with_raw_boxes": 0}
    assert not _blind_suspected_from_final_stats(final_rs=rs, blind_score=0.9, blind_score_threshold=0.7)


def test_suspected_true_when_no_boxes_and_high_score():
    rs = {"yolo_raw_boxes_total": 0, "yolo_frames_with_tracks": 0, "yolo_frames_with_raw_boxes": 0}
    assert _blind_suspected_from_final_stats(final_rs=rs, blind_score=0.5, blind_score_threshold=0.7)
