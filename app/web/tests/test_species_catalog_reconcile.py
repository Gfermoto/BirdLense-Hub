"""Каталог видов: reconcile и allowlist."""

import pytest

from app_config.app_config import app_config
from models import Species, VideoSpecies, db
from services.species_catalog_reconcile_service import reconcile_species_catalog
from services.species_merge_service import merge_species_into


@pytest.fixture(autouse=True)
def _pw():
    old_a = app_config.get("general.settings_password")
    old_c = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    try:
        yield
    finally:
        app_config.set("general.settings_password", old_a)
        app_config.set("general.contributor_password", old_c)


def test_merge_species_into_moves_fks(app):
    from models import Video, SpeciesVisit
    from datetime import datetime, timezone

    with app.app_context():
        a = Species(name="MergeTarget ZZ")
        b = Species(name="MergeSource ZZ")
        db.session.add_all([a, b])
        db.session.flush()
        v = Video(
            processor_version="t",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            video_path="m/z.mp4",
        )
        db.session.add(v)
        db.session.flush()
        sv = SpeciesVisit(
            species_id=b.id,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            max_simultaneous=1,
        )
        db.session.add(sv)
        db.session.flush()
        db.session.add(
            VideoSpecies(
                video_id=v.id,
                species_id=b.id,
                species_visit_id=sv.id,
                start_time=0.0,
                end_time=1.0,
                confidence=0.9,
                source="video",
                track_id=1,
            ),
        )
        db.session.commit()
        aid, bid = a.id, b.id
        merge_species_into(bid, aid)
        db.session.commit()
        assert db.session.get(Species, bid) is None
        assert VideoSpecies.query.filter_by(species_id=aid).count() == 1
        assert SpeciesVisit.query.filter_by(species_id=aid).count() == 1


def test_merge_species_into_preserves_missing_target_metadata(app):
    with app.app_context():
        target = Species(
            name="MergeTarget Meta",
            description="",
            image_url=None,
            metadata_source=None,
            metadata_source_url=None,
        )
        source = Species(
            name="MergeSource Meta",
            description="Source description survives merge.",
            image_url="https://example.com/source.jpg",
            metadata_source="wikipedia",
            metadata_source_url="https://example.com/source",
        )
        db.session.add_all([target, source])
        db.session.commit()

        target_id = target.id
        source_id = source.id

        merge_species_into(source_id, target_id)
        db.session.commit()
        db.session.expire_all()

        merged = db.session.get(Species, target_id)
        assert merged is not None
        assert merged.description == "Source description survives merge."
        assert merged.image_url == "https://example.com/source.jpg"
        assert merged.metadata_source == "wikipedia"
        assert merged.metadata_source_url == "https://example.com/source"


def test_merge_duplicate_species_endpoint_preserves_missing_target_metadata(
    app,
    client,
    monkeypatch,
):
    import util as util_mod

    with app.app_context():
        target = Species(
            name="MergeTarget Endpoint",
            description="",
            image_url=None,
        )
        source = Species(
            name="MergeSource Endpoint",
            description="Endpoint description survives merge.",
            image_url="https://example.com/endpoint.jpg",
        )
        db.session.add_all([target, source])
        db.session.commit()
        target_id = target.id

    monkeypatch.setattr(
        util_mod,
        "load_species_canonical_mapping",
        lambda: {
            "MergeTarget Endpoint": "MergeTarget Endpoint",
            "MergeSource Endpoint": "MergeTarget Endpoint",
        },
    )

    response = client.post("/api/ui/system/merge-duplicate-species")
    assert response.status_code == 200
    body = response.get_json()
    assert body["merged"] >= 1

    with app.app_context():
        db.session.expire_all()
        merged = db.session.get(Species, target_id)
        assert merged is not None
        assert merged.description == "Endpoint description survives merge."
        assert merged.image_url == "https://example.com/endpoint.jpg"


def test_reconcile_dry_run_finds_duplicate_norm(app):
    with app.app_context():
        if Species.query.filter_by(name="DupTest A").first():
            pytest.skip("fixture collision")
        s1 = Species(name="DupTest A")
        s2 = Species(name="duptest a")
        db.session.add_all([s1, s2])
        db.session.commit()
        rep = reconcile_species_catalog(
            dry_run=True,
            merge_normalized_duplicate_names=True,
            reassign_suspects_to_unknown=False,
            duplicate_group_limit=500,
            app_config_get=app_config.get,
        )
        assert rep["merged_species_rows"] >= 1
        assert Species.query.filter_by(name="duptest a").count() == 1


def test_reconcile_endpoint(client):
    r = client.post(
        "/api/ui/system/species-catalog/reconcile",
        json={"dry_run": True, "merge_normalized_duplicate_names": True},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("dry_run") is True
    assert "merged_species_rows" in body
