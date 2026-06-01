from __future__ import annotations

from datetime import datetime, timezone


def _payload(trigger_source: str) -> dict:
    start_iso = datetime(
        2026, 5, 31, 12, 0, tzinfo=timezone.utc
    ).isoformat()
    end_iso = datetime(
        2026, 5, 31, 12, 0, 10, tzinfo=timezone.utc
    ).isoformat()
    return {
        "processor_version": "test-trigger-source",
        "start_time": start_iso,
        "end_time": end_iso,
        "video_path": "data/recordings/2026/05/31/120000/video.mp4",
        "spectrogram_path": None,
        "trigger_source": trigger_source,
        "species": [
            {
                "species_name": "Great Tit",
                "confidence": 0.81,
                "source": "video",
                "start_time": 0.1,
                "end_time": 1.5,
                "detection_provider": "yolo",
                "track_id": 11,
                "frames": [
                    {"t": 0.1, "bbox": [0.1, 0.1, 0.2, 0.2]},
                ],
            }
        ],
    }


def test_processor_ingest_persists_video_trigger_source(client, app):
    from models import Video, db

    with app.app_context():
        res = client.post("/api/processor/videos", json=_payload("frigate"))
        assert res.status_code == 201
        row = db.session.query(Video).order_by(Video.id.desc()).first()
        assert row is not None
        assert row.trigger_source == "frigate"


def test_processor_ingest_ignores_invalid_trigger_source(client, app):
    from models import Video, db

    with app.app_context():
        res = client.post("/api/processor/videos", json=_payload("birdnet"))
        assert res.status_code == 201
        row = db.session.query(Video).order_by(Video.id.desc()).first()
        assert row is not None
        assert row.trigger_source is None


def test_processor_ingest_infers_trigger_source_when_empty(client, app):
    from models import Video, db

    payload = _payload("")
    payload.pop("trigger_source", None)
    with app.app_context():
        res = client.post("/api/processor/videos", json=payload)
        assert res.status_code == 201
        row = db.session.query(Video).order_by(Video.id.desc()).first()
        assert row is not None
        assert row.trigger_source == "opencv"
