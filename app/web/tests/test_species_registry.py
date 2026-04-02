import pytest

from app_config.app_config import app_config
import services.species_registry_service as registry_mod
from services.species_registry_service import (
    enrich_species_metadata,
    repair_recently_reset_species_metadata,
    resolve_species_name,
)
from services.visit_processor import VisitProcessor
from models import Species, db


@pytest.fixture(autouse=True)
def _disable_settings_passwords_for_registry_tests():
    """Registry system endpoints are protected; disable passwords for this suite."""
    old_admin = app_config.get('general.settings_password')
    old_contrib = app_config.get('general.contributor_password')
    app_config.set('general.settings_password', '')
    app_config.set('general.contributor_password', '')
    try:
        yield
    finally:
        app_config.set('general.settings_password', old_admin)
        app_config.set('general.contributor_password', old_contrib)


class TestSpeciesRegistryApi:
    def test_species_registry_sync_endpoints_removed(self, client):
        enrich = client.post('/api/ui/system/species-registry/enrich-metadata', json={'limit': 10})
        repair = client.post('/api/ui/system/species-registry/repair-cards', json={'limit': 10})
        assert enrich.status_code == 404
        assert repair.status_code == 404

    def test_species_registry_seed_endpoint(self, client):
        r = client.post('/api/ui/system/species-registry/seed')
        assert r.status_code == 200
        body = r.get_json()
        assert body.get('ok') is True
        assert 'taxa_created' in body
        assert 'aliases_created' in body

    def test_species_registry_backfill_endpoint_dry_run(self, client):
        r = client.post('/api/ui/system/species-registry/backfill', json={'dry_run': True, 'limit': 50})
        assert r.status_code == 200
        body = r.get_json()
        assert body.get('ok') is True
        assert body.get('dry_run') is True
        assert 'processed' in body
        assert 'matched' in body
        assert 'unresolved' in body

    def test_species_registry_health_endpoint(self, client):
        r = client.get('/api/ui/system/species-registry/health')
        assert r.status_code == 200
        body = r.get_json()
        assert 'species_total' in body
        assert 'species_with_taxon' in body
        assert 'coverage_percent' in body
        assert body['species_with_taxon'] <= body['species_total']

    def test_species_registry_backfill_reaches_full_coverage(self, client):
        r = client.post('/api/ui/system/species-registry/backfill', json={'dry_run': False})
        assert r.status_code == 200
        stats = r.get_json()
        assert stats.get('ok') is True
        health = client.get('/api/ui/system/species-registry/health')
        assert health.status_code == 200
        hb = health.get_json()
        assert hb['species_total'] >= 1
        assert hb['coverage_percent'] == 100.0

    def test_species_registry_async_enrichment_status(self, client):
        start = client.post(
            '/api/ui/system/species-registry/enrich-metadata/start',
            json={'limit': 10, 'retry_failed_only': False},
        )
        assert start.status_code in (202, 409)
        status = client.get('/api/ui/system/species-registry/enrich-metadata/status')
        assert status.status_code == 200
        body = status.get_json()
        assert body.get('status') in ('idle', 'running', 'done', 'error')


class TestSpeciesResolverIntegration:
    def test_visit_processor_creates_canonical_hooded_crow(self, app):
        with app.app_context():
            vp = VisitProcessor(db, app.logger)
            sp = vp._get_or_create_species('Corvus cornix (Hooded Crow)')
            assert sp is not None
            assert sp.name == 'Hooded Crow'
            assert sp.taxon_id is not None

    def test_unresolved_name_is_logged_and_reported(self, client, app):
        with app.app_context():
            r = resolve_species_name('Totally Unknown Bird XYZ', source='test_case')
            assert r.found is False
            db.session.commit()
        api = client.get('/api/ui/system/species-registry/unresolved?limit=20')
        assert api.status_code == 200
        items = (api.get_json() or {}).get('items') or []
        assert any('Totally Unknown Bird XYZ' in (i.get('raw_name') or '') for i in items)


class TestSpeciesMetadataRepair:
    def test_enrich_species_metadata_treats_blank_description_as_missing(
        self,
        app,
        monkeypatch,
    ):
        with app.app_context():
            sp = Species(
                name='Blank Description Nuthatches',
                description='',
                image_url='https://example.com/existing.jpg',
                metadata_source=None,
                metadata_source_url=None,
            )
            db.session.add(sp)
            db.session.commit()

            def fake_update_species_info(target):
                assert target.id == sp.id
                target.description = 'Recovered description.'
                target.metadata_source = 'wikipedia'
                return True

            monkeypatch.setattr(
                registry_mod,
                'update_species_info_from_wiki',
                fake_update_species_info,
            )

            stats = enrich_species_metadata(limit=5000, dry_run=False)
            db.session.expire_all()
            enriched = db.session.get(Species, sp.id)

            assert stats['processed'] >= 1
            assert stats['updated'] >= 1
            assert enriched.description == 'Recovered description.'
            assert enriched.image_url == 'https://example.com/existing.jpg'

    def test_repair_recently_reset_species_metadata_restores_images(self, app, monkeypatch):
        with app.app_context():
            sp = Species(
                name='Test Reset Towhee',
                description='Existing description survives the bad reset.',
                image_url=None,
                metadata_source=None,
                metadata_source_url=None,
            )
            db.session.add(sp)
            db.session.commit()

            def fake_update_species_info(target):
                assert target.id == sp.id
                target.image_url = 'https://example.com/aberts.jpg'
                target.metadata_source = 'inaturalist'
                target.metadata_source_url = 'https://www.inaturalist.org/taxa/123'
                return True

            monkeypatch.setattr(
                registry_mod,
                'update_species_info_from_wiki',
                fake_update_species_info,
            )

            stats = repair_recently_reset_species_metadata(dry_run=False)
            db.session.expire_all()
            repaired = db.session.get(Species, sp.id)

            assert stats['processed'] == 1
            assert stats['repaired'] == 1
            assert repaired.image_url == 'https://example.com/aberts.jpg'
            assert repaired.metadata_source == 'inaturalist'

