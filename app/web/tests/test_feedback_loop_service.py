from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def test_detection_patch_writes_feedback_event(app, client):
    from models import DetectionFeedbackEvent, Species, Video, VideoSpecies, db

    with app.app_context():
        old_species = Species(name="Sparrow")
        new_species = Species(name="Great Tit")
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 1, 10, 0, 30, tzinfo=timezone.utc),
            video_path="data/recordings/fb/video.mp4",
        )
        db.session.add_all([old_species, new_species, video])
        db.session.flush()
        det = VideoSpecies(
            video_id=video.id,
            species_id=old_species.id,
            start_time=1.0,
            end_time=2.0,
            confidence=0.83,
            source="video",
            detection_provider="yolo",
            track_id=10,
            frames='[{"t":1.2,"bbox":[1,2,3,4]}]',
        )
        db.session.add(det)
        db.session.commit()
        det_id = det.id
        new_species_id = new_species.id

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.patch(
        f"/api/ui/detections/{det_id}",
        json={
            "species_id": new_species_id,
            "source": "video",
            "apply_scope": "single_track",
            "reason": "operator_fix",
        },
    )
    assert r.status_code == 200

    with app.app_context():
        row = DetectionFeedbackEvent.query.order_by(DetectionFeedbackEvent.id.desc()).first()
        assert row is not None
        assert row.action == "relabel"
        assert row.video_species_id == det_id
        assert row.from_species_name == "Sparrow"
        assert row.to_species_name == "Great Tit"
        assert row.trigger_source == "video"
        assert row.apply_scope == "single_track"


def test_feedback_loop_status_endpoint(client, app):
    from app_config.app_config import app_config
    from models import DetectionFeedbackEvent, db

    with app.app_context():
        db.session.add(
            DetectionFeedbackEvent(
                action="delete_as_background",
                trigger_source="unknowns",
                video_species_id=1,
                video_id=1,
                track_id=2,
                from_species_name="Bird",
                to_species_name="Background",
            )
        )
        db.session.commit()
        data_dir = Path(str(app_config.get("directories.data") or "data"))
        status_dir = data_dir / "feedback_exports"
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "latest_status.json").write_text(
            json.dumps(
                {
                    "schema": "feedback_learning_latest_status@v1",
                    "status": "ok",
                    "events_total": 10,
                    "exported_total": 8,
                }
            ),
            encoding="utf-8",
        )

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.get("/api/ui/system/feedback-loop/status")
    assert r.status_code == 200
    body = r.get_json()
    assert body["schema"] == "feedback_loop_status@v1"
    assert body["events_total"] >= 1
    assert body["events_delete_as_background"] >= 1
    assert body["latest_export"]["status"] == "ok"


def test_export_feedback_learning_dataset_contract(tmp_path: Path):
    from services.feedback_loop_service import export_feedback_learning_dataset

    db_path = tmp_path / "birdlense.db"
    data_dir = tmp_path / "data"
    output_dir = data_dir / "feedback_exports"
    crop_dir = data_dir / "dataset" / "train" / "Great_Tit"
    crop_dir.mkdir(parents=True, exist_ok=True)
    crop = crop_dir / "11_22_33.jpg"
    crop.write_bytes(b"jpeg")

    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE detection_feedback_event (
              id INTEGER PRIMARY KEY,
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
        con.execute(
            """
            INSERT INTO detection_feedback_event
            (id, created_at, action, video_species_id, video_id, track_id, from_species_name, to_species_name)
            VALUES (1, ?, 'relabel', 33, 11, 22, 'Bird', 'Great Tit')
            """,
            (datetime.now(timezone.utc).isoformat(),),
        )
        con.commit()
    finally:
        con.close()

    out = export_feedback_learning_dataset(
        db_path=str(db_path),
        data_dir=str(data_dir),
        output_dir=str(output_dir),
        since_hours=24,
        limit=100,
        dry_run=False,
        export_tag="nightly_20260501",
    )
    assert out["schema"] == "feedback_learning_export@v1"
    assert out["export_tag"] == "nightly_20260501"
    assert out["events_total"] == 1
    assert out["exported_total"] == 1
    manifest = Path(out["export_root"]) / "manifest.json"
    assert manifest.is_file()
    assert out["export_root"].endswith("feedback_export_nightly_20260501")


def test_export_feedback_learning_dataset_missing_table_updates_latest_status(tmp_path: Path):
    from services.feedback_loop_service import export_feedback_learning_dataset

    db_path = tmp_path / "birdlense.db"
    sqlite3.connect(str(db_path)).close()
    data_dir = tmp_path / "data"
    output_dir = data_dir / "feedback_exports"

    out = export_feedback_learning_dataset(
        db_path=str(db_path),
        data_dir=str(data_dir),
        output_dir=str(output_dir),
        since_hours=24,
        limit=100,
        dry_run=True,
    )
    assert out["status"] == "missing_table"
    latest = output_dir / "latest_status.json"
    assert latest.is_file()
    status = json.loads(latest.read_text(encoding="utf-8"))
    assert status["status"] == "missing_table"


def test_delete_detection_writes_background_feedback(app, client):
    from models import DetectionFeedbackEvent, Species, Video, VideoSpecies, db

    with app.app_context():
        species = Species(name="Bird")
        video = Video(
            processor_version="t",
            start_time=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 1, 12, 0, 30, tzinfo=timezone.utc),
            video_path="data/recordings/fb/delete.mp4",
        )
        db.session.add_all([species, video])
        db.session.flush()
        det = VideoSpecies(
            video_id=video.id,
            species_id=species.id,
            start_time=1.0,
            end_time=2.0,
            confidence=0.51,
            source="video",
            detection_provider="yolo",
            track_id=99,
        )
        db.session.add(det)
        db.session.commit()
        det_id = det.id

    with client.session_transaction() as sess:
        sess["access_role"] = "contributor"
    r = client.delete(
        f"/api/ui/detections/{det_id}",
        json={"source": "video", "reason": "false_positive"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["detection_id"] == det_id

    with app.app_context():
        assert db.session.get(VideoSpecies, det_id) is None
        row = DetectionFeedbackEvent.query.order_by(DetectionFeedbackEvent.id.desc()).first()
        assert row is not None
        assert row.action == "delete_as_background"
        assert row.to_species_name == "Background"
