"""Unit tests for ``services.processor_ingest.video_ingest``."""

from datetime import datetime, timezone

import pytest

from services.processor_ingest.video_ingest import prepare_processor_video


@pytest.fixture
def _patch_stat_ok(monkeypatch):
    def _stat(path: str):
        return True, "/resolved/" + path, None

    monkeypatch.setattr(
        "services.processor_ingest.video_ingest.stat_recording_layout_file",
        _stat,
    )


def test_prepare_rejects_invalid_datetime(_patch_stat_ok):
    r = prepare_processor_video(
        {
            "start_time": "not-a-date",
            "end_time": "2020-01-01T00:00:00+00:00",
            "video_path": "data/recordings/2026/01/01/12-00-00/video.mp4",
            "species": [{"species_name": "X", "confidence": 0.9, "start_time": 0, "end_time": 1}],
        },
        min_confidence=0.05,
    )
    assert r[0] is False
    assert r[1] == {"error": "Invalid datetime format"}


def test_prepare_rejects_below_min_confidence(_patch_stat_ok):
    t = datetime.now(timezone.utc).isoformat()
    r = prepare_processor_video(
        {
            "start_time": t,
            "end_time": t,
            "video_path": "data/recordings/2026/01/01/12-00-00/video.mp4",
            "species": [
                {"species_name": "X", "confidence": 0.01, "start_time": 0, "end_time": 1},
            ],
        },
        min_confidence=0.05,
    )
    assert r[0] is False
    assert r[2] == 400
    assert "threshold" in r[1].get("error", "")


def test_prepare_success(_patch_stat_ok):
    t = datetime.now(timezone.utc).isoformat()
    r = prepare_processor_video(
        {
            "start_time": t,
            "end_time": t,
            "video_path": "data/recordings/2026/01/01/12-00-00/video.mp4",
            "species": [
                {"species_name": "Great Tit", "confidence": 0.9, "start_time": 0, "end_time": 1},
            ],
        },
        min_confidence=0.05,
    )
    assert r[0] is True
    pv = r[1]
    assert pv.video_path.endswith("video.mp4")
    assert "Great Tit" in (pv.species_list[0].get("species_name") or "")
