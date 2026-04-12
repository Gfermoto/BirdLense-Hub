"""Tests for GET /api/ui/settings/ebird-species-mapping-suggestions."""

from unittest.mock import patch


class TestEbirdMappingSuggestionsEndpoint:
    def test_no_api_key(self, app, client):
        from app_config.app_config import app_config
        from services import ebird_region_service

        with app.app_context():
            old_a = app_config.get("general.settings_password")
            old_c = app_config.get("general.contributor_password")
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            app_config.set("secrets.ebird_api_key", "")
            ebird_region_service._REGION_TOP_CACHE.clear()
            try:
                r = client.get("/api/ui/settings/ebird-species-mapping-suggestions")
            finally:
                app_config.set("general.settings_password", old_a or "")
                app_config.set("general.contributor_password", old_c or "")
        assert r.status_code == 200
        assert r.json["ebird_api_configured"] is False
        assert r.json["suggestions"] == []

    def test_case_variant_in_suggestions(self, app, client):
        from app_config.app_config import app_config
        from models import Species, db
        from services import ebird_region_service

        canon = "EbirdSuggest CaseVariant 136"
        ebird_form = canon.lower()

        with app.app_context():
            old_a = app_config.get("general.settings_password")
            old_c = app_config.get("general.contributor_password")
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            ebird_region_service._REGION_TOP_CACHE.clear()
            app_config.set("secrets.ebird_api_key", "test-key-suggestions")
            if Species.query.filter_by(name=canon).first() is None:
                db.session.add(Species(name=canon))
                db.session.commit()
            try:

                def fake_top(_api_key: str, _region: str):
                    return [ebird_form]

                with patch(
                    "services.ebird_mapping_suggestions.get_region_top_species_cached",
                    fake_top,
                ):
                    r = client.get("/api/ui/settings/ebird-species-mapping-suggestions")
            finally:
                app_config.set("general.settings_password", old_a or "")
                app_config.set("general.contributor_password", old_c or "")
        assert r.status_code == 200
        data = r.json
        assert data["ebird_api_configured"] is True
        assert data["top_count"] == 1
        assert len(data["suggestions"]) == 1
        row = data["suggestions"][0]
        assert row["ebird_name"] == ebird_form
        assert row["birdlense_name"] == canon
        assert row["kind"] == "case_variant"

    def test_resolved_by_exact_name_not_listed(self, app, client):
        from app_config.app_config import app_config
        from models import Species, db
        from services import ebird_region_service

        name = "EbirdSuggest Exact Match 136"
        with app.app_context():
            old_a = app_config.get("general.settings_password")
            old_c = app_config.get("general.contributor_password")
            app_config.set("general.settings_password", "")
            app_config.set("general.contributor_password", "")
            ebird_region_service._REGION_TOP_CACHE.clear()
            app_config.set("secrets.ebird_api_key", "test-key-suggestions")
            if Species.query.filter_by(name=name).first() is None:
                db.session.add(Species(name=name))
                db.session.commit()
            try:

                def fake_top(_api_key: str, _region: str):
                    return [name]

                with patch(
                    "services.ebird_mapping_suggestions.get_region_top_species_cached",
                    fake_top,
                ):
                    r = client.get("/api/ui/settings/ebird-species-mapping-suggestions")
            finally:
                app_config.set("general.settings_password", old_a or "")
                app_config.set("general.contributor_password", old_c or "")
        assert r.status_code == 200
        assert r.json["suggestions"] == []

    def test_403_when_settings_locked(self, app, client):
        from app_config.app_config import app_config

        with app.app_context():
            app_config.set("general.settings_password", "secret-test-lock-136")
        try:
            r = client.get("/api/ui/settings/ebird-species-mapping-suggestions")
            assert r.status_code == 403
            assert "error" in r.json
        finally:
            with app.app_context():
                app_config.set("general.settings_password", "")
