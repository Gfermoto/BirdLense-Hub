"""Фильтрация мусора и allowlist при создании Species."""

import pytest

from app_config.app_config import app_config
from models import Species, db
from services.visit_processor import VisitProcessor


@pytest.fixture(autouse=True)
def _restore_config():
    old_strict = app_config.get('species.catalog_strict_ingest')
    old_file = app_config.get('species.catalog_allowlist_file')
    yield
    app_config.set('species.catalog_strict_ingest', old_strict)
    app_config.set('species.catalog_allowlist_file', old_file)


def test_blocklisted_ingest_goes_to_unknown(app, monkeypatch):
    with app.app_context():
        app_config.set('species.catalog_strict_ingest', False)
        if not Species.query.filter_by(name='Birds').first():
            db.session.add(Species(name='Birds'))
            db.session.commit()
        if not Species.query.filter_by(name='Unknown').first():
            db.session.add(Species(name='Unknown', parent_id=Species.query.filter_by(name='Birds').first().id))
            db.session.commit()

        vp = VisitProcessor(db, app.logger)
        sp = vp._get_or_create_species('toilet')
        assert sp is not None
        assert sp.name == 'Unknown'


def test_strict_allowlist_blocks_unknown_class(app, monkeypatch):
    import services.visit_processor as vp_mod

    with app.app_context():
        app_config.set('species.catalog_strict_ingest', True)
        monkeypatch.setattr(
            vp_mod,
            'load_catalog_allowlist_norm_keys',
            lambda _get: frozenset({'parus major (great tit)'}),
        )
        if not Species.query.filter_by(name='Birds').first():
            db.session.add(Species(name='Birds'))
            db.session.commit()
        if not Species.query.filter_by(name='Unknown').first():
            db.session.add(
                Species(
                    name='Unknown',
                    parent_id=Species.query.filter_by(name='Birds').first().id,
                ),
            )
            db.session.commit()

        vp = VisitProcessor(db, app.logger)
        sp = vp._get_or_create_species('Cyanocitta cristata (Blue Jay)')
        assert sp is not None
        assert sp.name == 'Unknown'
