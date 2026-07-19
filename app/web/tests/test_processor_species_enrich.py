"""RC2 processor enrich PATCH (no manually_corrected)."""

from __future__ import annotations

from datetime import datetime, timezone

from models import Species, Video, VideoSpecies, db
from services.detection_species_correction_service import apply_processor_species_enrich


def test_processor_enrich_updates_species_without_manual_flag(app):
    with app.app_context():
        bird = Species(name="Bird")
        tit = Species(name="Great Tit Enrich")
        db.session.add_all([bird, tit])
        db.session.flush()
        video = Video(
            processor_version="test",
            video_path="/tmp/enrich.mp4",
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
            confidence=0.4,
            source="video",
            track_id=7,
            manually_corrected=False,
        )
        db.session.add(det)
        db.session.commit()

        err, ok = apply_processor_species_enrich(
            db.session,
            app.logger,
            video_id=int(video.id),
            detection_id=int(det.id),
            species_id=int(tit.id),
            confidence=0.91,
        )
        assert err is None
        assert ok is not None
        assert ok.get("manually_corrected") is False
        db.session.refresh(det)
        assert int(det.species_id) == int(tit.id)
        assert det.manually_corrected is False
        assert float(det.confidence) == 0.91


def test_processor_enrich_skips_manually_corrected(app):
    with app.app_context():
        bird = Species(name="Bird")
        tit = Species(name="Skip Enrich Tit")
        db.session.add_all([bird, tit])
        db.session.flush()
        video = Video(
            processor_version="test",
            video_path="/tmp/enrich-skip.mp4",
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
            confidence=0.4,
            source="video",
            track_id=8,
            manually_corrected=True,
        )
        db.session.add(det)
        db.session.commit()

        err, ok = apply_processor_species_enrich(
            db.session,
            app.logger,
            video_id=int(video.id),
            detection_id=int(det.id),
            species_id=int(tit.id),
        )
        assert err is None
        assert ok is not None
        assert ok.get("skipped") is True
        db.session.refresh(det)
        assert int(det.species_id) == int(bird.id)
