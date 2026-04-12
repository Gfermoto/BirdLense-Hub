"""Тесты сводки перегенерации треков."""

from web.services.track_regen_service import summarize_track_regen_detections


def test_summarize_empty():
    """Пустой список детекций."""
    s = summarize_track_regen_detections([])
    assert s["track_count"] == 0
    assert s["detections_with_frames"] == 0
    assert s["tracks_overlay_expected"] is False


def test_summarize_with_frames():
    """Счётчик кадров и флаг overlay."""
    s = summarize_track_regen_detections(
        [
            {"species_name": "A", "frames": [{"f": 1}]},
            {"species_name": "B", "frames": []},
        ]
    )
    assert s["track_count"] == 2
    assert s["detections_with_frames"] == 1
    assert s["tracks_overlay_expected"] is True
