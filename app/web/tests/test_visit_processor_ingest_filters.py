"""Tests for strict allowlist ingest and visit grouping safeguards."""

from datetime import datetime

import pytest

from app_config.app_config import app_config
from models import Species, SpeciesVisit, Video, VideoSpecies, db
from services.visit_processor import VisitProcessor


@pytest.fixture(autouse=True)
def _restore_config():
    old_strict = app_config.get("species.catalog_strict_ingest")
    old_file = app_config.get("species.catalog_allowlist_file")
    yield
    app_config.set("species.catalog_strict_ingest", old_strict)
    app_config.set("species.catalog_allowlist_file", old_file)


def test_no_strict_allows_any_name(app, monkeypatch):
    """Without strict mode, arbitrary class names may create catalog entries."""
    with app.app_context():
        app_config.set("species.catalog_strict_ingest", False)
        if not Species.query.filter_by(name="Birds").first():
            db.session.add(Species(name="Birds"))
            db.session.commit()
        vp = VisitProcessor(db, app.logger)
        sp = vp._get_or_create_species("SomeUnknownBirdXYZ")
        assert sp is not None
        assert sp.name != "Unknown"


def test_strict_allowlist_routes_unknown_placeholder_to_bird_review(app, monkeypatch):
    """Classifier Unknown placeholder must become generic Bird for manual review."""
    import services.species_identity_service as identity_mod

    with app.app_context():
        app_config.set("species.catalog_strict_ingest", True)
        monkeypatch.setattr(
            identity_mod,
            "load_catalog_allowlist_norm_keys",
            lambda _get: frozenset({"parus major (great tit)"}),
        )
        if not Species.query.filter_by(name="Birds").first():
            db.session.add(Species(name="Birds"))
            db.session.commit()
        if not Species.query.filter_by(name="Bird").first():
            db.session.add(
                Species(
                    name="Bird",
                    parent_id=Species.query.filter_by(name="Birds").first().id,
                ),
            )
            db.session.commit()

        vp = VisitProcessor(db, app.logger)
        sp = vp._get_or_create_species("Unknown")
        assert sp is not None
        assert sp.name == "Bird"


def test_strict_allowlist_fails_closed_when_allowlist_missing(app, monkeypatch):
    """Strict ingest must not create arbitrary species when allowlist is unavailable."""
    import services.species_identity_service as identity_mod

    with app.app_context():
        app_config.set("species.catalog_strict_ingest", True)
        monkeypatch.setattr(
            identity_mod,
            "load_catalog_allowlist_norm_keys",
            lambda _get: None,
        )
        if not Species.query.filter_by(name="Birds").first():
            db.session.add(Species(name="Birds"))
            db.session.commit()
        if not Species.query.filter_by(name="Unknown").first():
            db.session.add(
                Species(
                    name="Unknown",
                    parent_id=Species.query.filter_by(name="Birds").first().id,
                ),
            )
            db.session.commit()

        vp = VisitProcessor(db, app.logger)
        sp = vp._get_or_create_species("Knob Billed Duck")
        assert sp is not None
        assert sp.name == "Unknown"


def test_strict_allowlist_still_blocks_real_off_allowlist_species(app, monkeypatch):
    """Real off-allowlist species should still go to Unknown, not generic Bird."""
    import services.species_identity_service as identity_mod

    with app.app_context():
        app_config.set("species.catalog_strict_ingest", True)
        monkeypatch.setattr(
            identity_mod,
            "load_catalog_allowlist_norm_keys",
            lambda _get: frozenset({"parus major (great tit)"}),
        )
        if not Species.query.filter_by(name="Birds").first():
            db.session.add(Species(name="Birds"))
            db.session.commit()
        if not Species.query.filter_by(name="Unknown").first():
            db.session.add(
                Species(
                    name="Unknown",
                    parent_id=Species.query.filter_by(name="Birds").first().id,
                ),
            )
            db.session.commit()

        vp = VisitProcessor(db, app.logger)
        sp = vp._get_or_create_species("Cyanocitta cristata (Blue Jay)")
        assert sp is not None
        assert sp.name == "Unknown"


def test_out_of_order_video_ingest_does_not_attach_to_future_visit(app):
    """Older detections must not attach to a visit created from a later clip."""
    with app.app_context():
        species = Species(name="Eurasian Jay")
        db.session.add(species)
        db.session.flush()

        later_video = Video(
            processor_version="test",
            start_time=datetime(2026, 4, 1, 8, 47, 0),
            end_time=datetime(2026, 4, 1, 8, 47, 30),
            video_path="data/recordings/2026/04/01/084700/video.mp4",
        )
        earlier_video = Video(
            processor_version="test",
            start_time=datetime(2026, 3, 25, 7, 13, 0),
            end_time=datetime(2026, 3, 25, 7, 13, 30),
            video_path="data/recordings/2026/03/25/071300/video.mp4",
        )
        db.session.add_all([later_video, earlier_video])
        db.session.flush()

        vp = VisitProcessor(db, app.logger, visit_timeout=60)

        later_visit, _ = vp.process_video_detection(
            species=species,
            video=later_video,
            detection_start=0.0,
            detection_end=12.0,
            confidence=0.98,
        )
        earlier_visit, _ = vp.process_video_detection(
            species=species,
            video=earlier_video,
            detection_start=0.0,
            detection_end=12.6,
            confidence=0.97,
        )
        db.session.flush()

        assert later_visit.id != earlier_visit.id
        assert SpeciesVisit.query.count() == 2


def test_out_of_order_video_ingest_within_timeout_rewinds_visit_start(app):
    """Near out-of-order detections may reuse a visit, but start_time must rewind."""
    with app.app_context():
        species = Species(name="Great Tit")
        db.session.add(species)
        db.session.flush()

        later_video = Video(
            processor_version="test",
            start_time=datetime(2026, 4, 1, 8, 47, 0),
            end_time=datetime(2026, 4, 1, 8, 47, 30),
            video_path="data/recordings/2026/04/01/084700/video.mp4",
        )
        earlier_video = Video(
            processor_version="test",
            start_time=datetime(2026, 4, 1, 8, 46, 30),
            end_time=datetime(2026, 4, 1, 8, 47, 0),
            video_path="data/recordings/2026/04/01/084630/video.mp4",
        )
        db.session.add_all([later_video, earlier_video])
        db.session.flush()

        vp = VisitProcessor(db, app.logger, visit_timeout=60)

        visit_from_later, _ = vp.process_video_detection(
            species=species,
            video=later_video,
            detection_start=5.0,
            detection_end=10.0,
            confidence=0.98,
        )
        visit_from_earlier, _ = vp.process_video_detection(
            species=species,
            video=earlier_video,
            detection_start=0.0,
            detection_end=5.0,
            confidence=0.97,
        )
        db.session.flush()

        assert visit_from_later.id == visit_from_earlier.id
        assert visit_from_earlier.start_time.replace(tzinfo=None) == datetime(
            2026,
            4,
            1,
            8,
            46,
            30,
        )


def test_visit_eligible_false_creates_detection_without_visit(app):
    """Review-only rows must not create SpeciesVisit sessions."""
    with app.app_context():
        if not Species.query.filter_by(name="Birds").first():
            db.session.add(Species(name="Birds"))
        species = Species(name="Generic Bird Review")
        video = Video(
            processor_version="test",
            start_time=datetime(2026, 4, 7, 12, 0, 0),
            end_time=datetime(2026, 4, 7, 12, 0, 10),
            video_path="data/recordings/2026/04/07/120000/video.mp4",
        )
        db.session.add_all([species, video])
        db.session.commit()

        vp = VisitProcessor(db, app.logger, visit_timeout=60)
        vp.process_detections(
            video,
            [
                {
                    "species_name": species.name,
                    "start_time": 0.0,
                    "end_time": 2.0,
                    "confidence": 0.4,
                    "source": "video",
                    "visit_eligible": False,
                    "notification_eligible": False,
                    "track_id": 1,
                    "frames": [],
                }
            ],
        )
        db.session.commit()

        assert SpeciesVisit.query.count() == 0
        row = VideoSpecies.query.filter_by(video_id=video.id).one()
        assert row.species_visit_id is None
