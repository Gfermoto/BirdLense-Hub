from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

PROC_SECRET = "pytest-processor-trigger-source"


@pytest.fixture(autouse=True)
def _processor_secret_env(monkeypatch):
    monkeypatch.setenv("PROCESSOR_SECRET", PROC_SECRET)
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.setenv("FLASK_ENV", "testing")


@pytest.fixture
def proc_headers():
    return {
        "X-Processor-Token": PROC_SECRET,
        "Content-Type": "application/json",
    }


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


def _touch_video_file(video_path: str) -> None:
    assert video_path.startswith("data/recordings/")
    app_root = Path(__file__).resolve().parents[2]
    full = app_root / video_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")


def test_processor_ingest_persists_video_trigger_source(
    client,
    app,
    proc_headers,
):
    from models import Video, db

    body = _payload("frigate")
    _touch_video_file(str(body["video_path"]))
    with app.app_context():
        res = client.post(
            "/api/processor/videos",
            json=body,
            headers=proc_headers,
        )
        assert res.status_code == 201
        row = db.session.query(Video).order_by(Video.id.desc()).first()
        assert row is not None
        assert row.trigger_source == "frigate"


def test_processor_ingest_ignores_invalid_trigger_source(client, app, proc_headers):
    from models import Video, db

    body = _payload("birdnet")
    _touch_video_file(str(body["video_path"]))
    with app.app_context():
        res = client.post(
            "/api/processor/videos",
            json=body,
            headers=proc_headers,
        )
        assert res.status_code == 201
        row = db.session.query(Video).order_by(Video.id.desc()).first()
        assert row is not None
        assert row.trigger_source is None


def test_processor_ingest_infers_trigger_source_when_empty(
    client,
    app,
    proc_headers,
):
    from models import Video, db

    payload = _payload("")
    payload.pop("trigger_source", None)
    _touch_video_file(str(payload["video_path"]))
    with app.app_context():
        res = client.post(
            "/api/processor/videos",
            json=payload,
            headers=proc_headers,
        )
        assert res.status_code == 201
        row = db.session.query(Video).order_by(Video.id.desc()).first()
        assert row is not None
        assert row.trigger_source == "opencv"
