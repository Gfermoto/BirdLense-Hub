"""Ingest must not demote established species when strict allowlist is narrow."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app_config.app_config import app_config
from models import Species, SpeciesVisit, Video, VideoSpecies, db
from services.species_identity_service import SpeciesIdentityService


@pytest.fixture(autouse=True)
def _restore_strict():
    old = app_config.get("species.catalog_strict_ingest")
    yield
    app_config.set("species.catalog_strict_ingest", old)


def test_existing_observed_species_not_demoted_to_unknown(app, monkeypatch):
    import services.species_identity_service as identity_mod
    from services.species_catalog.vocabulary import SpeciesVocabularySnapshot

    narrow = SpeciesVocabularySnapshot(
        classifier_engine="efficientnet_b2",
        classifier_class_count=1,
        classifier_norm_keys=frozenset({"eurasian magpie"}),
        arbitration_norm_keys=frozenset(),
        project_norm_keys=frozenset({"eurasian magpie"}),
    )

    with app.app_context():
        app_config.set("species.catalog_strict_ingest", True)
        monkeypatch.setattr(identity_mod, "get_species_vocabulary_snapshot", lambda: narrow)

        birds = Species.query.filter_by(name="Birds").first()
        if not birds:
            birds = Species(name="Birds")
            db.session.add(birds)
            db.session.flush()
        from tests.conftest import get_or_create_species

        jay = get_or_create_species("Eurasian Jay", parent_id=birds.id, active=False)
        now = datetime.now(timezone.utc)
        video = Video(
            processor_version="test",
            video_path="/tmp/t.mp4",
            start_time=now,
            end_time=now,
        )
        db.session.add(video)
        db.session.flush()
        visit = SpeciesVisit(
            species_id=jay.id,
            start_time=video.start_time,
            end_time=video.end_time,
        )
        db.session.add(visit)
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=video.id,
                species_id=jay.id,
                species_visit_id=visit.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.5,
                source="video",
            ),
        )
        db.session.commit()

        svc = SpeciesIdentityService(db, app.logger)
        resolved = svc.resolve_or_create_species("Eurasian Jay", source="test")
        assert resolved is not None
        assert resolved.id == jay.id
        assert resolved.name == "Eurasian Jay"
