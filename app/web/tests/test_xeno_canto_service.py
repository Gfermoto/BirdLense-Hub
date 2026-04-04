"""Unit tests for Xeno-canto service (no real HTTP)."""
import requests

import services.xeno_canto_service as xcs


class TestSearchTermFromSpeciesName:
    def test_common_name_in_parentheses(self):
        assert xcs._search_term_from_species_name(
            'Garrulus glandarius (Eurasian Jay)',
        ) == 'Eurasian Jay'

    def test_plain_name(self):
        assert xcs._search_term_from_species_name('Robin') == 'Robin'

    def test_empty(self):
        assert xcs._search_term_from_species_name('') == ''
        assert xcs._search_term_from_species_name('  ') == ''


class TestFetchRecordings:
    def test_empty_when_term_empty(self, monkeypatch):
        calls = []
        monkeypatch.setattr(xcs.requests, 'get', lambda *a, **k: calls.append(1))
        assert xcs.fetch_recordings('') == []
        assert xcs.fetch_recordings('   ') == []
        assert calls == []

    def test_parses_ok_response(self, monkeypatch):
        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    'recordings': [
                        {
                            'id': '42',
                            'file': 'https://xeno-canto.org/42/download',
                            'en': 'song',
                            'type': 'call',
                            'rec': 'recorder',
                            'cnt': 'PL',
                        },
                        {
                            'id': '43',
                            'file': 'not-a-url',
                            'en': 'x',
                            'type': '',
                            'rec': '',
                            'cnt': '',
                        },
                    ],
                }

        monkeypatch.setattr(xcs.requests, 'get', lambda *a, **k: Resp())
        out = xcs.fetch_recordings('Blackbird', limit=5)
        assert len(out) == 1
        assert out[0]['id'] == '42'
        assert out[0]['file'].startswith('https://')

    def test_escapes_quotes_in_query(self, monkeypatch):
        captured = {}

        def capture_get(url, params=None, timeout=None):
            captured['params'] = dict(params or {})
            class Resp:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {'recordings': []}

            return Resp()

        monkeypatch.setattr(xcs.requests, 'get', capture_get)
        xcs.fetch_recordings('Test "quoted" bird', limit=2)
        q = captured['params'].get('query', '')
        # Inner quotes in the species term must be escaped for the API query string.
        assert 'quoted' in q
        assert '\\"' in q

    def test_returns_empty_on_request_error(self, monkeypatch):
        def boom(*a, **k):
            raise requests.RequestException('offline')

        monkeypatch.setattr(xcs.requests, 'get', boom)
        assert xcs.fetch_recordings('Robin') == []

    def test_returns_empty_on_bad_json(self, monkeypatch):
        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                raise ValueError('not json')

        monkeypatch.setattr(xcs.requests, 'get', lambda *a, **k: Resp())
        assert xcs.fetch_recordings('Robin') == []
