from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from models import SessionRuntimeMetrics, Species, Video, VideoSpecies, db


def _seed(app):
    with app.app_context():
        sp = Species(name="Robin", active=True)
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        video = Video(
            processor_version="test",
            start_time=start,
            end_time=start + timedelta(seconds=20),
            video_path="/tmp/a.mp4",
            behavior_label="alert",
            behavior_shadow_label="feeding",
            behavior_shadow_confidence=0.66,
        )
        db.session.add_all([sp, video])
        db.session.flush()
        vs = VideoSpecies(
            video_id=video.id,
            species_id=sp.id,
            start_time=0.2,
            end_time=3.2,
            confidence=0.27,
            source="video",
            detection_provider="yolo",
            track_id=11,
            frames=json.dumps([{"t": 0.2, "bbox": [0.1, 0.2, 0.4, 0.5]}]),
        )
        rt = SessionRuntimeMetrics(
            camera_id="cam-a",
            yolo_frames_ran=100,
            session_extended_by_frigate_only=52,
            payload_json=json.dumps(
                {
                    "yolo_blind_score": 0.72,
                    "yolo_frames_ran": 100,
                    "session_extended_by_frigate_only": 52,
                }
            ),
        )
        db.session.add_all([vs, rt])
        db.session.commit()


def test_labelling_flow(client, app):
    _seed(app)
    mine = client.post("/api/ui/labelling/cases/mine", json={"lookback_hours": 48})
    assert mine.status_code == 200, mine.get_data(as_text=True)
    assert mine.get_json()["created"] >= 1

    rows = client.get("/api/ui/labelling/cases?status=all")
    assert rows.status_code == 200
    body = rows.get_json()
    assert body["count"] >= 1
    first = body["items"][0]

    patch = client.patch(f"/api/ui/labelling/cases/{first['id']}", json={"status": "approved"})
    assert patch.status_code == 200
    assert patch.get_json()["status"] == "approved"

    exp = client.post("/api/ui/labelling/export", json={"format": "yolo", "status": "approved"})
    assert exp.status_code == 200
    payload = exp.get_json()
    assert payload["format"] == "yolo"
    assert payload["version"].startswith("v")

    fb = client.post(
        f"/api/ui/labelling/cases/{first['id']}/feedback",
        json={"action": "confirm_behavior", "behavior_tag": "feeding"},
    )
    assert fb.status_code == 200, fb.get_data(as_text=True)
    assert fb.get_json()["action"] == "confirm_behavior"
