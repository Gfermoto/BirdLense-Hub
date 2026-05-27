"""Unit tests for static pinned track rejection."""

from track_geometry import StaticPinnedTrackConfig, static_pinned_track_reason


def _track(frames, *, start=0.0, end=10.0):
    return {"start_time": start, "end_time": end, "frames": frames}


def test_static_pinned_track_rejected_when_bbox_frozen():
    frames = [
        {"timestamp": float(i), "bbox": [0.40, 0.30, 0.48, 0.38]}
        for i in range(12)
    ]
    reason = static_pinned_track_reason(_track(frames), StaticPinnedTrackConfig())
    assert reason is not None
    assert "rejected_static_pinned_track" in reason


def test_moving_track_not_rejected():
    frames = [
        {"timestamp": 0.0, "bbox": [0.10, 0.30, 0.18, 0.38]},
        {"timestamp": 1.0, "bbox": [0.30, 0.30, 0.38, 0.38]},
        {"timestamp": 2.0, "bbox": [0.50, 0.30, 0.58, 0.38]},
        {"timestamp": 3.0, "bbox": [0.70, 0.30, 0.78, 0.38]},
        {"timestamp": 4.0, "bbox": [0.85, 0.30, 0.93, 0.38]},
        {"timestamp": 5.0, "bbox": [0.90, 0.35, 0.98, 0.43]},
        {"timestamp": 6.0, "bbox": [0.92, 0.40, 1.00, 0.48]},
        {"timestamp": 7.0, "bbox": [0.94, 0.45, 1.00, 0.53]},
    ]
    reason = static_pinned_track_reason(_track(frames, end=8.0), StaticPinnedTrackConfig())
    assert reason is None


def test_short_frozen_track_skipped():
    frames = [{"timestamp": float(i), "bbox": [0.4, 0.3, 0.48, 0.38]} for i in range(12)]
    reason = static_pinned_track_reason(
        _track(frames, end=2.0),
        StaticPinnedTrackConfig(min_duration_sec=4.0),
    )
    assert reason is None
