import pytest

from app_config.app_config import app_config
import services.species_catalog.registry as registry_mod
from services.species_registry_service import (
    _rotate_need_slice,
    enrich_species_metadata,
    repair_recently_reset_species_metadata,
    resolve_species_name,
)
from services.visit_processor import VisitProcessor
from models import Species, db


def _species_row_for_metadata_test(name: str, **fields) -> Species:
    """Reuse registry seed rows when present; avoid UNIQUE(name) across ordered tests."""
    sp = Species.query.filter_by(name=name).first()
    if sp is None:
        sp = Species(name=name, **fields)
        db.session.add(sp)
    else:
        for key, value in fields.items():
            setattr(sp, key, value)
    db.session.commit()
    return sp


@pytest.fixture(autouse=True)
def _disable_settings_passwords_for_registry_tests(client, monkeypatch):
    """Registry system endpoints are protected; open access like other settings smoke tests.

    - Clear passwords **after** ``client`` exists so values from ``user_config.yaml`` apply first.
    - Drop ``BIRDLENSE_ENV`` / ``FLASK_ENV`` production markers: empty passwords deny access
      in production (``auth.settings_check_access``), which matches CI and developer shells.
    """
    monkeypatch.delenv("BIRDLENSE_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    old_admin = app_config.get("general.settings_password")
    old_contrib = app_config.get("general.contributor_password")
    app_config.set("general.settings_password", "")
    app_config.set("general.contributor_password", "")
    try:
        yield
    finally:
        app_config.set("general.settings_password", old_admin)
        app_config.set("general.contributor_password", old_contrib)


def test_rotate_need_slice_for_catalog_repair_window():
    assert _rotate_need_slice([1, 2, 3, 4, 5], 0) == [1, 2, 3, 4, 5]
    assert _rotate_need_slice([1, 2, 3, 4, 5], 2) == [3, 4, 5, 1, 2]
    assert _rotate_need_slice([1, 2, 3], 5) == [3, 1, 2]


class TestSpeciesRegistryApi:
    def test_species_registry_sync_endpoints_removed(self, client):
        enrich = client.post("/api/ui/system/species-registry/enrich-metadata", json={"limit": 10})
        repair = client.post("/api/ui/system/species-registry/repair-cards", json={"limit": 10})
        assert enrich.status_code == 404
        assert repair.status_code == 404

    def test_species_registry_seed_endpoint(self, client):
        r = client.post("/api/ui/system/species-registry/seed")
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("ok") is True
        assert "taxa_created" in body
        assert "aliases_created" in body

    def test_species_registry_backfill_endpoint_dry_run(self, client):
        r = client.post("/api/ui/system/species-registry/backfill", json={"dry_run": True, "limit": 50})
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("ok") is True
        assert body.get("dry_run") is True
        assert "processed" in body
        assert "matched" in body
        assert "unresolved" in body

    def test_species_registry_health_endpoint(self, client):
        r = client.get("/api/ui/system/species-registry/health")
        assert r.status_code == 200
        body = r.get_json()
        assert "species_total" in body
        assert "species_with_taxon" in body
        assert "coverage_percent" in body
        assert "species_resolution_mismatches" in body
        assert "duplicate_name_group_count" in body
        assert "drift_scan_limit" in body
        assert "drift_scan_complete" in body
        assert body["species_with_taxon"] <= body["species_total"]

    def test_species_registry_health_reports_resolution_drift(self, client, app):
        from models import SpeciesAlias, SpeciesTaxon

        with app.app_context():
            target = SpeciesTaxon(
                taxon_key="target-finch",
                common_name="Target Finch",
                scientific_name="Targetus finchus",
            )
            wrong = SpeciesTaxon(
                taxon_key="wrong-finch",
                common_name="Wrong Finch",
                scientific_name="Wrongus finchus",
            )
            db.session.add_all([target, wrong])
            db.session.flush()
            db.session.add(
                SpeciesAlias(
                    alias="Mapped Finch",
                    alias_key="mapped finch",
                    taxon_id=target.id,
                )
            )
            drifted = Species(name="Mapped Finch", taxon_id=wrong.id)
            duplicate = Species(name="mapped finch")
            unresolved = Species(name="Ghost Bird Name")
            db.session.add_all([drifted, duplicate, unresolved])
            db.session.commit()

        r = client.get("/api/ui/system/species-registry/health")
        assert r.status_code == 200
        body = r.get_json()
        assert body["species_resolution_mismatches"] >= 1
        assert body["species_unresolved_rows"] >= 1
        assert body["duplicate_name_group_count"] >= 1
        assert body["mismatch_samples"]

    def test_species_registry_backfill_reaches_full_coverage(self, client):
        r = client.post("/api/ui/system/species-registry/backfill", json={"dry_run": False})
        assert r.status_code == 200
        stats = r.get_json()
        assert stats.get("ok") is True
        health = client.get("/api/ui/system/species-registry/health")
        assert health.status_code == 200
        hb = health.get_json()
        assert hb["species_total"] >= 1
        assert hb["coverage_percent"] == 100.0

    def test_species_registry_async_enrichment_status(self, client):
        start = client.post(
            "/api/ui/system/species-registry/enrich-metadata/start",
            json={"limit": 10, "retry_failed_only": False},
        )
        assert start.status_code in (202, 409)
        status = client.get("/api/ui/system/species-registry/enrich-metadata/status")
        assert status.status_code == 200
        body = status.get_json()
        assert body.get("status") in ("idle", "running", "done", "error")


class TestSpeciesResolverIntegration:
    def test_visit_processor_creates_canonical_hooded_crow(self, app):
        with app.app_context():
            vp = VisitProcessor(db, app.logger)
            sp = vp._get_or_create_species("Corvus cornix (Hooded Crow)")
            assert sp is not None
            assert sp.name == "Hooded Crow"
            assert sp.taxon_id is not None

    def test_resolve_species_name_matches_normalized_common_name_without_alias(self, app):
        from models import SpeciesTaxon

        with app.app_context():
            taxon = SpeciesTaxon(
                taxon_key="great-tit-normalized",
                common_name="Great-Tit",
                scientific_name="Parus major",
            )
            db.session.add(taxon)
            db.session.commit()

            resolved = resolve_species_name("great tit", source="test_case")
            assert resolved.found is True
            assert resolved.taxon is not None
            assert resolved.method in ("alias_key", "common_name_normalized")
            assert resolved.taxon.common_name == "Great Tit"

    def test_unresolved_name_is_logged_and_reported(self, client, app):
        with app.app_context():
            r = resolve_species_name("Totally Unknown Bird XYZ", source="test_case")
            assert r.found is False
            db.session.commit()
        api = client.get("/api/ui/system/species-registry/unresolved?limit=20")
        assert api.status_code == 200
        items = (api.get_json() or {}).get("items") or []
        assert any("Totally Unknown Bird XYZ" in (i.get("raw_name") or "") for i in items)

    def test_species_identity_attaches_external_aliases_to_existing_taxon(self, app):
        from models import SpeciesAlias, SpeciesTaxon
        from services.species_identity_service import SpeciesIdentityService

        with app.app_context():
            taxon = SpeciesTaxon.query.filter_by(common_name="Great Tit").first()
            assert taxon is not None, "registry seed should provide Great Tit taxon"
            species = Species.query.filter_by(name="Great Tit").first()
            assert species is not None, "registry seed should provide Great Tit species row"
            if species.taxon_id != taxon.id:
                species.taxon_id = taxon.id
                db.session.commit()

            svc = SpeciesIdentityService(db, app.logger)
            resolved = svc.resolve_or_create_species(
                "Great Tit",
                source="ingest:frigate",
                audit_aliases=["great_tit", "Parus major (Great Tit)"],
                audit_scientific_names=["Parus major"],
            )
            db.session.commit()

            assert resolved is not None
            assert resolved.name == "Great Tit"
            alias_keys = {row.alias_key for row in SpeciesAlias.query.filter_by(taxon_id=taxon.id).all()}
            assert "great tit" in alias_keys
            assert "parus major" in alias_keys


class TestSpeciesMetadataRepair:
    def test_enrich_species_metadata_treats_blank_description_as_missing(
        self,
        app,
        monkeypatch,
    ):
        with app.app_context():
            sp = Species(
                name="Blank Description Nuthatches",
                description="",
                image_url="https://example.com/existing.jpg",
                metadata_source=None,
                metadata_source_url=None,
            )
            db.session.add(sp)
            db.session.commit()

            def fake_update_species_info(target):
                assert target.id == sp.id
                target.description = "Recovered description."
                target.metadata_source = "wikipedia"
                return True

            monkeypatch.setattr(
                registry_mod,
                "enrich_species_card_metadata",
                fake_update_species_info,
            )

            stats = enrich_species_metadata(limit=5000, dry_run=False)
            db.session.expire_all()
            enriched = db.session.get(Species, sp.id)

            assert stats["processed"] >= 1
            assert stats["updated"] >= 1
            assert enriched.description == "Recovered description."
            assert enriched.image_url == "https://example.com/existing.jpg"

    def test_repair_recently_reset_species_metadata_restores_images(self, app, monkeypatch):
        with app.app_context():
            sp = Species(
                name="Test Reset Towhee",
                description="Existing description survives the bad reset.",
                image_url=None,
                metadata_source=None,
                metadata_source_url=None,
            )
            db.session.add(sp)
            db.session.commit()

            def fake_update_species_info(target):
                assert target.id == sp.id
                target.image_url = "https://example.com/aberts.jpg"
                target.metadata_source = "inaturalist"
                target.metadata_source_url = "https://www.inaturalist.org/taxa/123"
                return True

            monkeypatch.setattr(
                registry_mod,
                "enrich_species_card_metadata",
                fake_update_species_info,
            )

            stats = repair_recently_reset_species_metadata(dry_run=False)
            db.session.expire_all()
            repaired = db.session.get(Species, sp.id)

            assert stats["processed"] == 1
            assert stats["repaired"] == 1
            assert repaired.image_url == "https://example.com/aberts.jpg"
            assert repaired.metadata_source == "inaturalist"


def test_catalog_cards_coverage_counts_per_allowlist_line(app, monkeypatch):
    """Regression: metrics vs allowlist length must be per file line, not deduped species only."""
    from services.species_registry_service import catalog_cards_coverage_snapshot

    with app.app_context():
        sp = Species(
            name="Testus birdus (Test Bird)",
            description="d",
            image_url="https://example.com/t.jpg",
            metadata_source=None,
            metadata_source_url=None,
        )
        db.session.add(sp)
        db.session.commit()

        monkeypatch.setattr(
            registry_mod,
            "load_catalog_allowlist_names",
            lambda _get: (
                "Testus birdus (Test Bird)",
                "Testus birdus (Test Bird)",
                "No Such Species Xyzabc",
            ),
        )

        snap = catalog_cards_coverage_snapshot(app_config.get)
        assert snap["allowlist_total"] == 3
        assert snap["allowlist_lines_matched"] == 2
        assert snap["species_matched"] == 1
        assert snap["with_image"] == 2
        assert snap["with_description"] == 2
        assert snap["complete_cards"] == 2
        assert snap["completion_percent"] == round((2.0 / 3.0) * 100.0, 2)


def test_materialize_allowlist_normalizes_caps_common_name(app, monkeypatch):
    from services.species_registry_service import ensure_allowlist_species_materialized

    with app.app_context():
        monkeypatch.setattr(
            registry_mod,
            "load_catalog_allowlist_names",
            lambda _get: ("PARUS MAJOR (GREAT TIT)",),
        )
        monkeypatch.setattr(
            registry_mod,
            "normalize_catalog_display_name",
            lambda value, _mapping: "Great Tit" if str(value).strip().upper() == "GREAT TIT" else value,
        )

        out = ensure_allowlist_species_materialized(
            app_config.get,
            fill_metadata=False,
            dry_run=False,
            limit=10,
        )
        row = Species.query.filter_by(name="Great Tit").first()
        assert out["allowlist_total"] == 1
        assert row is not None


def test_update_species_info_from_wiki_whitespace_image_counts_as_empty(
    app,
    monkeypatch,
):
    """Полировка считает image_url из пробелов пустым; enrich не должен выходить раньше времени."""
    import species_metadata as sm

    with app.app_context():
        sp = Species(
            name="Whitespace Image Finch",
            description="",
            image_url=" \t  ",
            metadata_source=None,
            metadata_source_url=None,
        )
        db.session.add(sp)
        db.session.commit()

        def fake_wiki(title, *, use_cache=True):
            return ("https://example.com/w.jpg", "Real description for finch.")

        monkeypatch.setattr(sm, "get_wikipedia_image_and_description", fake_wiki)
        monkeypatch.setattr(
            sm,
            "get_inaturalist_image_and_description",
            lambda title: (None, None, None),
        )

        ok = sm.update_species_info_from_wiki(sp)
        db.session.commit()
        db.session.refresh(sp)
        assert ok is True
        assert "example.com/w.jpg" in (sp.image_url or "")
        assert "Real description" in (sp.description or "")


def test_update_species_info_from_wiki_applies_manual_great_tit_override(app, monkeypatch):
    import species_metadata as sm

    with app.app_context():
        sp = _species_row_for_metadata_test(
            "Great Tit",
            description="",
            image_url="",
            metadata_source=None,
            metadata_source_url=None,
        )

        monkeypatch.setattr(sm, "get_wikipedia_image_and_description", lambda *_a, **_k: (None, None))
        monkeypatch.setattr(sm, "get_inaturalist_image_and_description", lambda *_a, **_k: (None, None, None))

        ok = sm.update_species_info_from_wiki(sp)
        db.session.commit()
        db.session.refresh(sp)
        assert ok is True
        assert "inaturalist-open-data.s3.amazonaws.com/photos/340613122/medium.jpg" in (sp.image_url or "")


def test_update_species_info_from_wiki_applies_manual_eurasian_blue_tit_override(app, monkeypatch):
    import species_metadata as sm

    with app.app_context():
        sp = _species_row_for_metadata_test(
            "Eurasian Blue Tit",
            description="",
            image_url="",
            metadata_source=None,
            metadata_source_url=None,
        )

        monkeypatch.setattr(sm, "get_wikipedia_image_and_description", lambda *_a, **_k: (None, None))
        monkeypatch.setattr(sm, "get_inaturalist_image_and_description", lambda *_a, **_k: (None, None, None))

        ok = sm.update_species_info_from_wiki(sp)
        db.session.commit()
        db.session.refresh(sp)
        assert ok is True
        assert "inaturalist-open-data.s3.amazonaws.com/photos/41677354/medium.jpeg" in (sp.image_url or "")


def test_wikipedia_extract_rejects_human_hair_article():
    import species_metadata as sm

    blob = "Natural red hair is associated with the MC1R gene in human populations. " * 8
    assert sm.wikipedia_extract_rejects_wrong_topic(blob) is True


def test_wikipedia_extract_accepts_duck_article():
    import species_metadata as sm

    t = (
        "The redhead (Aythya americana) is a medium-sized diving duck. "
        "The scientific name is derived from Greek. The canvasback is migratory. "
        "Males have distinctive breeding plumage with a coppery head."
    )
    assert sm.wikipedia_extract_rejects_wrong_topic(t) is False


def test_disambiguated_wikipedia_title_redhead_variants():
    import species_metadata as sm

    assert sm.disambiguated_wikipedia_title_for_display_name("Redhead") == "Aythya americana"
    assert sm.disambiguated_wikipedia_title_for_display_name("Redhead (Breeding male)") == "Aythya americana"


def test_typo_catalog_wikipedia_title_maps_misspellings():
    import species_metadata as sm

    assert sm._typo_catalog_wikipedia_title("KILLDEAR") == "Killdeer"
    assert sm._typo_catalog_wikipedia_title("MANDRIN DUCK") == "Mandarin duck"
    assert sm._typo_catalog_wikipedia_title("AUCKLAND SHAQ") == "Auckland shag"
    assert sm._typo_catalog_wikipedia_title("ASIAN DOLLARD BIRD") == "Asian dollarbird"
    assert sm._typo_catalog_wikipedia_title("Go Away Bird") == "Gray go-away-bird"
    assert sm._typo_catalog_wikipedia_title("Black Cockato") == "Red-tailed black cockatoo"
    assert sm._typo_catalog_wikipedia_title("Unknown Typo Bird") is None


def test_wikipedia_query_titles_includes_typo_catalog_title():
    import species_metadata as sm
    from types import SimpleNamespace

    sp = SimpleNamespace(name="KILLDEAR", taxon=None)
    titles = sm._wikipedia_query_titles_for_species(sp)
    assert "Killdeer" in titles


def test_update_species_info_from_wiki_skips_bad_wikipedia_then_accepts_good(app, monkeypatch):
    import species_metadata as sm

    monkeypatch.setattr(sm, "_wikipedia_query_titles_for_species", lambda sp: ["BadTitle", "GoodTitle"])
    monkeypatch.setattr(
        sm,
        "get_inaturalist_image_and_description",
        lambda title: (None, None, None),
    )

    def fake_wiki(title, *, use_cache=True):
        if title == "BadTitle":
            return (
                "https://example.com/human.jpg",
                "Natural red hair is associated with the MC1R gene in human populations. " * 8,
            )
        if title == "GoodTitle":
            return (
                "https://example.com/bird.jpg",
                "The redhead (Aythya americana) is a medium-sized diving duck. " * 5,
            )
        return None, None

    monkeypatch.setattr(sm, "get_wikipedia_image_and_description", fake_wiki)

    with app.app_context():
        sp = _species_row_for_metadata_test("Redhead", description="", image_url="")
        sm._wiki_meta_cache.clear()
        ok = sm.update_species_info_from_wiki(sp)
        db.session.commit()
        db.session.refresh(sp)
        assert ok is True
        assert "bird.jpg" in (sp.image_url or "")
        assert "Aythya" in (sp.description or "")


def test_update_species_info_from_wiki_clears_suspicious_existing_description(app, monkeypatch):
    import species_metadata as sm

    bad = "Natural red hair is associated with the MC1R gene in human populations. " * 8
    monkeypatch.setattr(sm, "_wikipedia_query_titles_for_species", lambda sp: ["GoodTitle"])
    monkeypatch.setattr(
        sm,
        "get_wikipedia_image_and_description",
        lambda title, use_cache=True: (
            "https://example.com/bird.jpg",
            "The redhead (Aythya americana) is a medium-sized diving duck. " * 5,
        ),
    )
    monkeypatch.setattr(sm, "get_inaturalist_image_and_description", lambda title: (None, None, None))

    with app.app_context():
        sp = _species_row_for_metadata_test(
            "Redhead",
            description=bad,
            image_url="https://example.com/wrong.jpg",
        )
        sm._wiki_meta_cache.clear()
        ok = sm.update_species_info_from_wiki(sp)
        db.session.commit()
        db.session.refresh(sp)
        assert ok is True
        assert "Aythya" in (sp.description or "")
        assert "bird.jpg" in (sp.image_url or "")
