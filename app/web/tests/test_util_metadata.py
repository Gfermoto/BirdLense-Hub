"""Регрессия: разбор URL/имён без небезопасных подстроков (CodeQL)."""

import web.util as util_mod
from web.util import (
    _extract_common_for_hierarchy,
    get_inaturalist_image_and_description,
    infer_metadata_source_fields,
)


class TestInferMetadataSourceFields:
    """Source provenance inference helpers."""

    def test_wikipedia_by_hostname(self):
        """Detect Wikipedia by trusted hostname."""
        src, url = infer_metadata_source_fields(
            'Turdus merula',
            'https://upload.wikimedia.org/wikipedia/commons/x.jpg',
            None,
        )
        assert src == 'wikipedia'
        assert 'wikipedia.org' in (url or '')

    def test_inaturalist_host(self):
        """Detect iNaturalist by canonical hostname."""
        src, url = infer_metadata_source_fields(
            None,
            'https://www.inaturalist.org/observations/1',
            None,
        )
        assert src == 'inaturalist'
        assert 'inaturalist.org' in (url or '')

    def test_inaturalist_open_data_bucket(self):
        """Treat open-data asset as iNaturalist, but without fake taxon page."""
        src, url = infer_metadata_source_fields(
            None,
            'https://inaturalist-open-data.s3.amazonaws.com/photo.jpg',
            None,
        )
        assert src == 'inaturalist'
        assert url is None

    def test_unknown_host_no_substring_bypass(self):
        """Do not trust attacker-controlled lookalike URLs."""
        src, orig = infer_metadata_source_fields(
            None,
            'https://evil-example.net/inaturalist.org',
            None,
        )
        assert src is None
        assert orig is None

    def test_no_inaturalist_via_query_string_on_untrusted_host(self):
        """Подстрока inaturalist-open-data в query не должна включать чужой host (регрессия SSRF-эвристики)."""
        src, orig = infer_metadata_source_fields(
            None,
            'https://evil.example/photo?ref=inaturalist-open-data',
            None,
        )
        assert src is None
        assert orig is None


class TestExtractCommonForHierarchy:
    """Hierarchy label normalization."""

    def test_parentheses(self):
        """Extract display name from parenthetical hierarchy labels."""
        assert _extract_common_for_hierarchy('X (Northern Cardinal)') == (
            'Northern Cardinal'
        )
        assert _extract_common_for_hierarchy('Plain') == 'Plain'
        assert _extract_common_for_hierarchy(
            'Bald Eagle (Adult, subadult)',
        ) == 'Adult, subadult'


class TestINaturalistMetadata:
    """iNaturalist metadata fallback behavior."""

    def test_filters_non_bird_taxa(self, monkeypatch):
        """Ignore non-bird taxa even if iNaturalist returns them."""
        seen = {}

        class _Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    'results': [
                        {
                            'id': 1,
                            'name': 'Kitchen Knife',
                            'iconic_taxon_name': 'Mollusca',
                            'default_photo': {
                                'medium_url': 'https://example.com/knife.jpg',
                            },
                            'wikipedia_summary': 'Not a bird',
                        },
                    ],
                }

        def fake_get(url, params=None, timeout=None, headers=None):
            seen['params'] = params
            return _Resp()

        monkeypatch.setattr(util_mod.requests, 'get', fake_get)

        image_url, description, source_url = (
            get_inaturalist_image_and_description("Abert's Towhee")
        )

        assert seen['params']['iconic_taxa'] == 'Aves'
        assert image_url is None
        assert description is None
        assert source_url is None
