"""ML/CV operator APIs that do not require new model weights."""

from __future__ import annotations

from datetime import datetime, timezone


def test_video_action_events_weak_labels_from_tracks_and_weight(app, client):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Great Tit")
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 10, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/actions/video.mp4",
            scales_weight_delta_kg=-0.003,
        )
        db.session.add_all([species, video])
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=species.id,
                start_time=2.0,
                end_time=12.0,
                confidence=0.88,
                source="video",
                detection_provider="yolo",
                track_id=42,
            )
        )
        db.session.commit()
        vid = video.id

    r = client.get(f"/api/ui/videos/{vid}/action-events")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    labels = [e["label"] for e in body["events"]]
    assert labels == ["arrival", "possible_feeding", "departure"]
    assert body["events"][1]["evidence"]["scales_weight_delta_kg"] == -0.003


def test_video_details_keeps_individual_nickname(app, client):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Blue Tit")
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 12, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/nickname/video.mp4",
        )
        db.session.add_all([species, video])
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=species.id,
                start_time=1.0,
                end_time=8.0,
                confidence=0.86,
                source="video",
                detection_provider="yolo",
                track_id=7,
                individual_nickname="Bluey",
            )
        )
        db.session.commit()
        vid = video.id

    r = client.get(f"/api/ui/videos/{vid}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["species"][0]["individual_nickname"] == "Bluey"


def test_patch_detection_sets_individual_nickname(app, client):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Sparrow")
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 12, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/nickname/patch.mp4",
        )
        db.session.add_all([species, video])
        db.session.flush()
        det = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=2.0,
            end_time=7.0,
            confidence=0.72,
            source="video",
            detection_provider="yolo",
            track_id=21,
        )
        db.session.add(det)
        db.session.commit()
        detection_id = det.id
        video_id = video.id

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    patch_resp = client.patch(
        f"/api/ui/detections/{detection_id}",
        json={
            "individual_nickname": "Маруся",
            "source": "video",
            "apply_scope": "single_track",
        },
    )
    assert patch_resp.status_code == 200
    patch_body = patch_resp.get_json()
    assert patch_body["individual_nickname"] == "Маруся"

    details_resp = client.get(f"/api/ui/videos/{video_id}")
    assert details_resp.status_code == 200
    body = details_resp.get_json()
    assert body["species"][0]["individual_nickname"] == "Маруся"


def test_active_learning_pool_preview_lists_uncertain_items(app, client):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Bird")
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 11, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 11, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/al/video.mp4",
        )
        db.session.add_all([species, video])
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=species.id,
                start_time=1.0,
                end_time=3.0,
                confidence=0.41,
                source="video",
                detection_provider="yolo",
                track_id=5,
                classifier_entropy=1.4,
                classifier_top1_top2_margin=0.02,
                classifier_needs_review=True,
                review_reason="classifier_uncertainty",
            )
        )
        db.session.commit()

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/system/active-learning/pool-preview?limit=5")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "active_learning_pool_preview@v1"
    assert body["items"][0]["review_reason"] == "classifier_uncertainty"
    assert body["items"][0]["classifier_entropy"] == 1.4


def test_reid_summary_handles_missing_sidecar_table(client):
    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/system/reid/summary")
    assert r.status_code == 200
    assert r.get_json()["available"] is False


def test_ml_runtime_reports_config_state(client):
    r = client.get("/api/ui/system/ml-runtime")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "ml_runtime_status@v1"
    assert "capture_backend_config" in body["video"]
    assert "inference_backend" in body["processor"]
