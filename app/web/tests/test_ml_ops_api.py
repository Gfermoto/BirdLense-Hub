"""ML/CV operator APIs that do not require new model weights."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import text


def test_video_action_events_endpoint_removed(app, client):
    from models import Video, db

    with app.app_context():
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 10, 1, 0, tzinfo=timezone.utc),
            video_path="data/recordings/actions/video.mp4",
        )
        db.session.add(video)
        db.session.commit()
        vid = video.id

    r = client.get(f"/api/ui/videos/{vid}/action-events")
    assert r.status_code == 404


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


def test_ml_runtime_reports_config_state(app, client):
    from app_config.app_config import app_config

    old_admin = app_config.get("general.settings_password")
    old_contrib = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    try:
        r = client.get("/api/ui/system/ml-runtime")
        assert r.status_code == 200
        body = r.get_json()
        assert body["schema"] == "ml_runtime_status@v1"
        assert "capture_backend_config" in body["video"]
        assert "record_hw_encode" in body["video"]
        assert "inference_backend" in body["processor"]
        assert "classifier_inference_backend" in body["processor"]
        assert "reid_runtime_enabled" in body["processor"]
        assert "welfare_runtime_enabled" in body["processor"]
    finally:
        app_config.set("general.settings_password", old_admin or "")
        app_config.set("general.contributor_password", old_contrib or "")


def test_dataset_streams_summary_endpoint(client):
    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/system/dataset-streams")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "dataset_streams_summary@v1"
    assert sorted(body["required_streams"]) == [
        "classifier",
        "detector",
        "reid",
    ]
    stream_index = {item["stream"]: item for item in body["streams"]}
    assert "reid" in stream_index
    assert stream_index["reid"]["export_policy"]["community_export_allowed"] is False
    assert stream_index["reid"]["export_policy"]["private_backup_only"] is True
    job_index = {item["stream"]: item for item in body["api_jobs"]}
    assert "export_to_community" in job_index["detector"]["operations"]
    assert "private_backup_only" in job_index["reid"]["operations"]


def test_classifier_calibration_report_endpoint(app, client, tmp_path):
    import sqlite3
    from app_config.app_config import app_config

    with app.app_context():
        prev_data_dir = app_config.get("directories.data")
        test_data_dir = str(tmp_path / "calibration-data")
        app_config.set("directories.data", test_data_dir)
        db_dir = Path(test_data_dir) / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "birdlense.db"
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            DROP TABLE IF EXISTS video_species;
            DROP TABLE IF EXISTS activity_log;
            CREATE TABLE video_species (
                id INTEGER PRIMARY KEY,
                video_id INTEGER,
                track_id INTEGER,
                confidence REAL,
                detection_provider TEXT,
                classifier_entropy REAL,
                classifier_top1_top2_margin REAL,
                classifier_needs_review INTEGER,
                review_reason TEXT
            );
            CREATE TABLE activity_log (
                id INTEGER PRIMARY KEY,
                type TEXT,
                data TEXT,
                created_at TEXT DEFAULT '2026-01-01'
            );
            """
        )
        conn.execute(
            """
            INSERT INTO video_species (
              id, video_id, track_id, confidence, detection_provider,
              classifier_entropy, classifier_top1_top2_margin,
              classifier_needs_review, review_reason
            )
            VALUES (10, 2001, 77, 0.41, 'yolo', 1.2, 0.01, 1, 'classifier_uncertainty')
            """
        )
        conn.execute(
            "INSERT INTO activity_log (type, data) VALUES ('species_correction', ?)",
            (
                json.dumps(
                    {
                        "detection_id": 10,
                        "from_species_name": "Wood Mouse",
                        "to_species_name": "Bird",
                        "source": "unknowns",
                    }
                ),
            ),
        )
        conn.commit()
        conn.close()

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/system/classifier-calibration-report?pair_limit=5")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "classifier_calibration_report@v1"
    assert body["available"] is True
    assert body["corrections_analyzed"] >= 1
    assert isinstance(body["top_confusion_pairs"], list)
    assert "calibration_metrics" in body
    assert "topk_metrics" in body
    assert "session_consensus" in body
    assert "unknown_ood_dashboard" in body
    assert "long_tail_report" in body
    with app.app_context():
        app_config.set("directories.data", prev_data_dir)


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
        species = Species(name="Great Tit ReID Match")
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
                    "model": "ornimetrics_reid",
                    "dim": 4,
                    "emb": json.dumps([1.0, 0.0, 0.0, 0.0]),
                    "name": species.name,
                    "label": d1.individual_nickname,
                    "schema": "embedding_schema@v1",
                    "mid": "ornimetrics:reid_embedder",
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
                    "model": "ornimetrics_reid",
                    "dim": 4,
                    "emb": json.dumps([0.99, 0.01, 0.0, 0.0]),
                    "name": species.name,
                    "label": d2.individual_nickname,
                    "schema": "embedding_schema@v1",
                    "mid": "ornimetrics:reid_embedder",
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


def test_similarity_summary_endpoint(app, client):
    from models import Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Blue Tit")
        v1 = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 12, 0, 20, tzinfo=timezone.utc),
            video_path="data/recordings/reid/s1.mp4",
        )
        v2 = Video(
            processor_version="t",
            start_time=datetime(2026, 4, 29, 12, 5, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 29, 12, 5, 20, tzinfo=timezone.utc),
            video_path="data/recordings/reid/s2.mp4",
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
            track_id=101,
            individual_nickname="Bird-A",
        )
        d2 = VideoSpecies(
            video_id=v2.id,
            species_id=species.id,
            start_time=1.5,
            end_time=3.5,
            confidence=0.92,
            source="video",
            track_id=102,
            individual_nickname="Bird-A",
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
                    "crop": f"/tmp/s1-{d1.id}.jpg",
                    "model": "ornimetrics_reid",
                    "dim": 4,
                    "emb": json.dumps([1.0, 0.0, 0.0, 0.0]),
                    "name": species.name,
                    "label": "bird-a",
                    "schema": "embedding_schema@v1",
                    "mid": "ornimetrics:reid_embedder",
                    "msha": "abcdabcdabcdabcd",
                    "cfp": "1111111111111111",
                    "cat": "2026-04-29T12:00:00Z",
                },
                {
                    "vsid": d2.id,
                    "vid": v2.id,
                    "sid": species.id,
                    "tid": d2.track_id,
                    "crop": f"/tmp/s2-{d2.id}.jpg",
                    "model": "ornimetrics_reid",
                    "dim": 4,
                    "emb": json.dumps([0.99, 0.01, 0.0, 0.0]),
                    "name": species.name,
                    "label": "bird-a",
                    "schema": "embedding_schema@v1",
                    "mid": "ornimetrics:reid_embedder",
                    "msha": "abcdabcdabcdabcd",
                    "cfp": "2222222222222222",
                    "cat": "2026-04-29T12:05:00Z",
                },
            ],
        )
        db.session.commit()

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/system/reid/similarity-summary?top_k=5&max_rows=200")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "similarity_summary@v1"
    assert body["similarity"]["available"] is True
    assert body["similarity"]["anchors_evaluated"] >= 1


def test_similarity_summary_without_reid_table(client):
    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/system/reid/similarity-summary")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "similarity_summary@v1"
    assert body["similarity"]["available"] is False


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


def test_feedback_loop_export_dry_run_endpoint(app, client, tmp_path, monkeypatch):
    from app_config.app_config import app_config
    import sqlite3

    with app.app_context():
        prev_data_dir = app_config.get("directories.data")
        app_config.set("directories.data", str(tmp_path))
        (tmp_path / "db").mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "db" / "birdlense.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS detection_feedback_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                action TEXT,
                trigger_source TEXT,
                apply_scope TEXT,
                reason TEXT,
                video_species_id INTEGER,
                video_id INTEGER,
                track_id INTEGER,
                from_species_id INTEGER,
                to_species_id INTEGER,
                from_species_name TEXT,
                to_species_name TEXT,
                detection_provider TEXT,
                confidence REAL,
                frames_json TEXT,
                crop_path TEXT,
                camera TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.post(
        "/api/ui/system/feedback-loop/export",
        json={
            "dry_run": True,
            "since_hours": 24,
            "limit": 10,
            "export_tag": "api_dry_run",
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "feedback_learning_export@v1"
    assert body["dry_run"] is True
    assert body["export_tag"] == "api_dry_run"
    assert "events_total" in body
    assert "export_root" in body
    with app.app_context():
        app_config.set("directories.data", prev_data_dir)


def test_feedback_loop_export_rejects_invalid_args(client):
    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.post("/api/ui/system/feedback-loop/export", json={"since_hours": 0})
    assert r.status_code == 400
    assert r.get_json()["error"] == "since_hours must be > 0"
