from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models import SessionRuntimeMetrics, Species, Video, VideoSpecies, db


def _seed(app):
    with app.app_context():
        Path("/tmp/a.mp4").write_bytes(b"test")
        sp = Species(name="Robin", active=True)
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        video = Video(
            processor_version="test",
            start_time=start,
            end_time=start + timedelta(seconds=20),
            video_path="/tmp/a.mp4",
            behavior_label="alert",
            behavior_confidence=0.96,
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
            individual_nickname="Синичка Соня",
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
    assert "pre_approved" in first
    assert "suggested_species" in first
    assert "suggested_behavior" in first
    assert any((row.get("individual_nickname") == "Синичка Соня") for row in body["items"])

    rows_media_only = client.get("/api/ui/labelling/cases?status=all&with_media_only=1")
    assert rows_media_only.status_code == 200
    media_body = rows_media_only.get_json()
    assert media_body["count"] >= 1

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

    batch = client.post(
        "/api/ui/labelling/batch-feedback",
        json={
            "operations": [
                {"kind": "feedback", "case_id": first["id"], "action": "tag_species", "species_tag": "Robin"},
                {"kind": "feedback", "case_id": first["id"], "action": "confirm_behavior", "behavior_tag": "feeding"},
                {"kind": "status", "case_id": first["id"], "status": "approved"},
            ]
        },
    )
    assert batch.status_code == 200, batch.get_data(as_text=True)
    assert batch.get_json()["ok"] is True
    assert batch.get_json()["count"] == 3

    semantic_flag = client.post(
        f"/api/ui/labelling/cases/{first['id']}/feedback",
        json={"action": "flag_semantic_error"},
    )
    assert semantic_flag.status_code == 200, semantic_flag.get_data(as_text=True)
    assert semantic_flag.get_json()["status"] == "semantic_review_required"


def test_bird_profiles_link_and_semantic_queue(client, app):
    _seed(app)
    mine = client.post("/api/ui/labelling/cases/mine", json={"lookback_hours": 48})
    assert mine.status_code == 200, mine.get_data(as_text=True)
    list_resp = client.get("/api/ui/labelling/cases?status=all")
    items = list_resp.get_json()["items"]
    case = next((row for row in items if row.get("video_species_id") is not None), None)
    assert case is not None
    detection_id = int(case["video_species_id"])

    create_resp = client.post(
        "/api/ui/bird-profiles",
        json={"display_name": "Синичка Лада"},
    )
    assert create_resp.status_code == 201, create_resp.get_data(as_text=True)
    profile_id = int(create_resp.get_json()["id"])

    link_resp = client.patch(
        f"/api/ui/detections/{detection_id}",
        json={"bird_profile_id": profile_id},
    )
    assert link_resp.status_code == 200, link_resp.get_data(as_text=True)
    assert int(link_resp.get_json()["bird_profile_id"]) == profile_id

    unlink_resp = client.patch(
        f"/api/ui/detections/{detection_id}",
        json={"bird_profile_id": None},
    )
    assert unlink_resp.status_code == 200, unlink_resp.get_data(as_text=True)
    assert unlink_resp.get_json()["bird_profile_id"] is None

    semantic_resp = client.patch(
        f"/api/ui/detections/{detection_id}",
        json={"semantic_review_required": True, "semantic_review_note": "species mismatch"},
    )
    assert semantic_resp.status_code == 200, semantic_resp.get_data(as_text=True)
    assert semantic_resp.get_json()["required"] is True

    now_ts = int(datetime.now(timezone.utc).timestamp())
    queue = client.get(
        f"/api/ui/unknowns?queue=expert&start_time={now_ts - 7200}&end_time={now_ts}&limit=50"
    )
    assert queue.status_code == 200, queue.get_data(as_text=True)
