"""GET /api/ui/videos/:id/fusion-trace — трассировка decision_trace (#272)."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def test_fusion_trace_404_unknown_video(client):
    r = client.get("/api/ui/videos/999999/fusion-trace")
    assert r.status_code == 404
    assert r.get_json().get("error")


def test_fusion_trace_no_log_returns_available_false(app, client):
    from models import Video, db

    with app.app_context():
        v = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 10, 12, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/fusion-trace/none.mp4",
        )
        db.session.add(v)
        db.session.commit()
        vid = v.id

    r = client.get(f"/api/ui/videos/{vid}/fusion-trace")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is False
    assert body.get("message") == "no_decision_trace"
    assert body.get("video_id") == vid


def test_fusion_trace_matches_by_video_id(app, client):
    from models import ActivityLog, Video, db

    with app.app_context():
        v = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 10, 12, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/fusion-trace/by-id.mp4",
        )
        db.session.add(v)
        db.session.flush()
        vid = v.id
        payload = {
            "video_id": vid,
            "video_path": v.video_path,
            "merge_window_seconds": 8,
            "accepted_tracks": [
                {
                    "track_id": 7,
                    "species_name": "Great Tit",
                    "accepted": True,
                    "confidence": 0.91,
                    "detector_label": "Bird",
                    "detector_confidence": 0.95,
                    "classifier_species_name": "Great Tit",
                    "classifier_confidence": 0.88,
                }
            ],
            "rejected_tracks": [],
            "accepted_track_count": 1,
            "rejected_track_count": 0,
        }
        db.session.add(ActivityLog(type="decision_trace", data=json.dumps(payload)))
        db.session.commit()

    r = client.get(f"/api/ui/videos/{vid}/fusion-trace")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    assert body["video_id"] == vid
    assert body.get("log_created_at")
    tracks = body.get("tracks") or []
    assert len(tracks) == 1
    assert tracks[0]["bucket"] == "accepted"
    assert tracks[0]["track_id"] == 7
    stages = [s["stage"] for s in tracks[0]["steps"]]
    assert "detector" in stages
    assert "classifier" in stages
    assert "outcome" in stages


def test_fusion_trace_path_fallback_without_video_id_in_payload(app, client):
    from models import ActivityLog, Video, db

    with app.app_context():
        v = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 10, 12, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/fusion-trace/legacy-path.mp4",
        )
        db.session.add(v)
        db.session.flush()
        vid = v.id
        payload = {
            "video_path": "recordings/fusion-trace/legacy-path.mp4",
            "accepted_tracks": [{"track_id": 1, "species_name": "Bird", "accepted": True, "confidence": 0.5}],
            "rejected_tracks": [],
        }
        db.session.add(ActivityLog(type="decision_trace", data=json.dumps(payload)))
        db.session.commit()

    r = client.get(f"/api/ui/videos/{vid}/fusion-trace")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    assert (body.get("tracks") or [])[0]["track_id"] == 1
