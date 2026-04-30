"""ML/CV operator APIs that do not require new model weights."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from sqlalchemy import text


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
    body = r.get_json()
    assert body["available"] is False
    assert body["schema"] == "reid_summary@v2"
    assert body["contract"]["status"] == "missing_table"


def test_ml_runtime_reports_config_state(client):
    r = client.get("/api/ui/system/ml-runtime")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "ml_runtime_status@v1"
    assert "capture_backend_config" in body["video"]
    assert "inference_backend" in body["processor"]
    assert "classifier_inference_backend" in body["processor"]


def test_video_reid_match_handles_missing_table(client):
    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/videos/1/reid-match")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.get_json()
        assert body["schema"] == "video_reid_match@v2"
        assert body["available"] is False


def test_video_reid_match_returns_candidate(app, client):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Great Tit")
        v1 = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 12, 0, 20, tzinfo=timezone.utc),
            video_path="data/recordings/reid/v1.mp4",
        )
        v2 = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 12, 5, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 12, 5, 20, tzinfo=timezone.utc),
            video_path="data/recordings/reid/v2.mp4",
        )
        db.session.add_all([species, v1, v2])
        db.session.flush()
        d1 = VideoSpecies(
            video_id=v1.id,
            species_id=species.id,
            start_time=1.0,
            end_time=3.0,
            confidence=0.9,
            source="video",
            track_id=11,
            individual_nickname="Соня",
        )
        d2 = VideoSpecies(
            video_id=v2.id,
            species_id=species.id,
            start_time=1.5,
            end_time=3.5,
            confidence=0.92,
            source="video",
            track_id=12,
            individual_nickname="Пятнышко",
        )
        db.session.add_all([d1, d2])
        db.session.flush()
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS reid_embedding (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_species_id INTEGER,
                    video_id INTEGER,
                    species_id INTEGER,
                    track_id INTEGER,
                    crop_path TEXT NOT NULL UNIQUE,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    species_name TEXT,
                    individual_label TEXT,
                    embedding_schema TEXT,
                    embedding_model_id TEXT,
                    embedding_model_sha16 TEXT,
                    crop_fingerprint_sha16 TEXT,
                    jsonl_created_at_utc TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.session.execute(
            text(
                "INSERT INTO reid_embedding "
                "(video_species_id, video_id, species_id, track_id, crop_path, model, dim, embedding_json, species_name, individual_label, "
                "embedding_schema, embedding_model_id, embedding_model_sha16, crop_fingerprint_sha16, jsonl_created_at_utc) "
                "VALUES (:vsid,:vid,:sid,:tid,:crop,:model,:dim,:emb,:name,:label,:schema,:mid,:msha,:cfp,:cat)"
            ),
            [
                {
                    "vsid": d1.id,
                    "vid": v1.id,
                    "sid": species.id,
                    "tid": d1.track_id,
                    "crop": f"/tmp/d1-{d1.id}.jpg",
                    "model": "dinov2",
                    "dim": 4,
                    "emb": json.dumps([1.0, 0.0, 0.0, 0.0]),
                    "name": species.name,
                    "label": d1.individual_nickname,
                    "schema": "embedding_schema@v1",
                    "mid": "torchhub:facebookresearch/dinov2:dinov2_vits14",
                    "msha": "abcdabcdabcdabcd",
                    "cfp": "1111111111111111",
                    "cat": "2026-04-29T12:00:00Z",
                },
                {
                    "vsid": d2.id,
                    "vid": v2.id,
                    "sid": species.id,
                    "tid": d2.track_id,
                    "crop": f"/tmp/d2-{d2.id}.jpg",
                    "model": "dinov2",
                    "dim": 4,
                    "emb": json.dumps([0.99, 0.01, 0.0, 0.0]),
                    "name": species.name,
                    "label": d2.individual_nickname,
                    "schema": "embedding_schema@v1",
                    "mid": "torchhub:facebookresearch/dinov2:dinov2_vits14",
                    "msha": "abcdabcdabcdabcd",
                    "cfp": "2222222222222222",
                    "cat": "2026-04-29T12:05:00Z",
                },
            ],
        )
        db.session.commit()
        vid = v1.id

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get(f"/api/ui/videos/{vid}/reid-match")
    assert r.status_code == 200
    body = r.get_json()
    assert body["available"] is True
    assert body["matches"]
    assert body["matches"][0]["candidate_video_id"] != vid


def test_detection_patch_updates_nickname(app, client):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Bird")
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 13, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 13, 0, 20, tzinfo=timezone.utc),
            video_path="data/recordings/nickname/video.mp4",
        )
        db.session.add_all([species, video])
        db.session.flush()
        det = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=1.0,
            end_time=2.0,
            confidence=0.9,
            source="video",
        )
        db.session.add(det)
        db.session.commit()
        det_id = det.id

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.patch(
        f"/api/ui/detections/{det_id}",
        json={"individual_nickname": "Пух"},
    )
    assert r.status_code == 200
    assert r.get_json()["individual_nickname"] == "Пух"
