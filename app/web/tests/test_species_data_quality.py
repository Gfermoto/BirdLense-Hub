"""Качество каталога видов: блоклист, exclude_suspects, отчёт."""

import pytest

from services.http_response_cache import bust_response_caches
from services.species_data_quality_service import (
    _load_suspect_blocklist_sets,
    build_data_quality_report,
    suspect_reasons_for_species,
)


@pytest.fixture(autouse=True)
def _clear_blocklist_cache():
    _load_suspect_blocklist_sets.cache_clear()
    yield
    _load_suspect_blocklist_sets.cache_clear()


def test_suspect_reasons_kitchen_knife():
    r = suspect_reasons_for_species('Kitchen Knife', None)
    assert r
    assert any('blocklist' in x for x in r)


def test_suspect_reasons_normal_bird_empty():
    assert suspect_reasons_for_species('Blue Jay', 'Blue Jay') == []


def test_build_report_has_structure(app):
    from models import db

    with app.app_context():
        rep = build_data_quality_report(
            db.session,
            suspect_limit=20,
            duplicate_group_limit=5,
        )
    assert 'species_total' in rep
    assert 'suspect_count' in rep
    assert 'suspects' in rep
    assert 'duplicate_name_groups' in rep
    assert 'hints' in rep


class TestSpeciesListExcludeSuspects:
    def test_exclude_suspects_hides_blocklisted_rows(self, app, client):
        from models import Species, db

        with app.app_context():
            junk = Species(name='Kitchen Knife DQ Test Row')
            good = Species(name='Unique Valid Finch DQ Test ZZ')
            db.session.add_all([junk, good])
            db.session.commit()
            jid, gid = junk.id, good.id

        bust_response_caches()
        r_all = client.get('/api/ui/species')
        r_ex = client.get('/api/ui/species', query_string={'exclude_suspects': '1'})
        assert r_all.status_code == 200
        assert r_ex.status_code == 200
        all_ids = {x['id'] for x in r_all.get_json()}
        ex_ids = {x['id'] for x in r_ex.get_json()}
        assert jid in all_ids
        assert gid in all_ids
        assert jid not in ex_ids
        assert gid in ex_ids
