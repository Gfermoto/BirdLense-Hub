"""Качество каталога видов: дубликаты, отчёт."""

from datetime import datetime, timezone

from services.species_data_quality_service import build_data_quality_report


def test_build_report_has_structure(app):
    from models import db

    with app.app_context():
        rep = build_data_quality_report(
            db.session,
            duplicate_group_limit=5,
        )
    assert "species_total" in rep
    assert "duplicate_name_group_count" in rep
    assert "duplicate_name_groups" in rep
    assert "hints" in rep


def test_species_ids_to_exclude_from_bird_catalog_filters_off_allowlist_active_species(
    app,
    monkeypatch,
):
    """Active off-allowlist species must disappear when UI asks to hide suspects."""
    from models import Species, SpeciesVisit, db
    from services import species_data_quality_service as mod

    monkeypatch.setattr(
        mod,
        "load_catalog_allowlist_norm_keys",
        lambda _get: frozenset({"parus major (great tit)", "great tit"}),
    )

    with app.app_context():
        allowed = Species(name="Parus major (Great Tit)")
        exotic = Species(name="Knob Billed Duck")
        db.session.add_all([allowed, exotic])
        db.session.flush()
        db.session.add_all(
            [
                SpeciesVisit(
                    species_id=allowed.id,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    max_simultaneous=1,
                ),
                SpeciesVisit(
                    species_id=exotic.id,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    max_simultaneous=1,
                ),
            ]
        )
        db.session.commit()
        allowed_id = allowed.id
        exotic_id = exotic.id

        excluded = mod.species_ids_to_exclude_from_bird_catalog(db.session)

    assert exotic_id in excluded
    assert allowed_id not in excluded


def test_build_report_ignores_duplicate_names_without_activity(app):
    from models import Species, SpeciesVisit, db

    with app.app_context():
        stale_a = Species(name="Ghost Bird", active=False)
        stale_b = Species(name="Ghost_Bird", active=False)
        live_a = Species(name="Live Bird", active=True)
        live_b = Species(name="Live_Bird", active=False)
        db.session.add_all([stale_a, stale_b, live_a, live_b])
        db.session.flush()
        db.session.add(
            SpeciesVisit(
                species_id=live_a.id,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                max_simultaneous=1,
            ),
        )
        db.session.add(
            SpeciesVisit(
                species_id=live_b.id,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                max_simultaneous=1,
            ),
        )
        db.session.commit()

        rep = build_data_quality_report(db.session, duplicate_group_limit=10)

    normalized_names = {item["normalized_name"] for item in rep["duplicate_name_groups"]}
    assert "ghost bird" not in normalized_names
    assert "live bird" in normalized_names
