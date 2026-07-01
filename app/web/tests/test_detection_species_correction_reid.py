"""Species corrections must keep ReID sidecar rows in sync."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from models import Species, Video, VideoSpecies, db
from services.detection_species_correction_service import apply_detection_species_patch


def test_species_patch_updates_reid_embedding_species(app):
    with app.app_context():
        bird = Species(name="Bird")
        robin = Species(name="ReID Patch Robin")
        db.session.add_all([bird, robin])
        db.session.flush()
        video = Video(
            processor_version="test",
            video_path="/tmp/reid-patch.mp4",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        )
        db.session.add(video)
        db.session.flush()
        det = VideoSpecies(
            video_id=video.id,
            species_id=bird.id,
            start_time=0.0,
            end_time=1.0,
            confidence=0.8,
            source="video",
            track_id=1,
        )
        db.session.add(det)
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO reid_embedding (
                    video_species_id, video_id, species_id, track_id, crop_path, model, dim,
                    embedding_json, species_name, individual_label
                ) VALUES (
                    :vsid, :vid, :sid, :tid, :crop, 'ornimetrics_reid', 3, :emb, 'Bird', NULL
                )
                """
            ),
            {
                "vsid": det.id,
                "vid": video.id,
                "sid": bird.id,
                "tid": det.track_id,
                "crop": "runtime://test/reid-patch",
                "emb": json.dumps([0.1, 0.2, 0.3]),
            },
        )
        db.session.commit()

        err, ok = apply_detection_species_patch(
            db.session,
            app.logger,
            int(det.id),
            {"species_id": int(robin.id), "apply_scope": "single_track", "source": "test"},
            app_obj_for_thread=app,
        )

        assert err is None
        assert ok is not None
        row = (
            db.session.execute(
                text("SELECT species_id, species_name FROM reid_embedding WHERE video_species_id=:vsid"),
                {"vsid": det.id},
            )
            .mappings()
            .one()
        )
        assert int(row["species_id"]) == int(robin.id)
        assert row["species_name"] == "ReID Patch Robin"
