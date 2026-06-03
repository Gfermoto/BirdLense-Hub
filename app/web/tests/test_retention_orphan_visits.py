"""Retention cascade must remove orphaned SpeciesVisit rows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import Species, SpeciesVisit, Video, VideoSpecies, db
from services.retention_service import run_retention


def test_retention_cascade_removes_orphan_visits(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    session_dir = rec_root / "2026" / "01" / "01" / "100000"
    session_dir.mkdir(parents=True)
    clip = session_dir / "video.mp4"
    clip.write_bytes(b"x" * 1024)

    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    now = datetime.now(timezone.utc)
    rel = "data/recordings/2026/01/01/100000/video.mp4"

    with app.app_context():
        from app_config.app_config import app_config

        species = Species(name="RetentionOrphanSpecies")
        db.session.add(species)
        db.session.flush()

        orphan_visit = SpeciesVisit(
            species_id=species.id,
            start_time=now - timedelta(days=10),
            end_time=now - timedelta(days=10) + timedelta(minutes=1),
            max_simultaneous=1,
        )
        video = Video(
            processor_version="test",
            start_time=now - timedelta(days=10),
            end_time=now - timedelta(days=10) + timedelta(seconds=30),
            video_path=rel,
            favorite=False,
        )
        db.session.add_all([orphan_visit, video])
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_visit_id=orphan_visit.id,
                species_id=species.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.9,
                source="video",
            )
        )
        db.session.commit()
        video_id = video.id
        visit_id = orphan_visit.id

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", 1)
        app_config.set("retention.max_gb", None)
        app_config.set("retention.protect_favorites", False)

        deleted, _ = run_retention(dry_run=False, mode="cascade")

        assert deleted == 1
        assert db.session.get(Video, video_id) is None
        assert db.session.get(SpeciesVisit, visit_id) is None

        app_config.set("retention.days", 90)


def test_retention_dry_run_previews_orphan_visits(app, tmp_path, monkeypatch):
    rec_root = tmp_path / "data" / "recordings"
    rec_root.mkdir(parents=True)

    monkeypatch.setattr("services.retention_service.recordings_dir", lambda: str(rec_root))
    monkeypatch.setattr("services.retention_service._recordings_dir", lambda: str(rec_root))

    now = datetime.now(timezone.utc)
    with app.app_context():
        from app_config.app_config import app_config

        species = Species(name="DryRunOrphanSpecies")
        db.session.add(species)
        db.session.flush()

        orphan_visit = SpeciesVisit(
            species_id=species.id,
            start_time=now - timedelta(days=1),
            end_time=now,
            max_simultaneous=1,
        )
        db.session.add(orphan_visit)
        db.session.commit()
        visit_id = orphan_visit.id

        app_config.set("retention.mode", "cascade")
        app_config.set("retention.days", None)
        app_config.set("retention.max_gb", None)

        run_retention(dry_run=True, mode="cascade")

        assert db.session.get(SpeciesVisit, visit_id) is not None

        app_config.set("retention.days", 90)
