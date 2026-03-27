"""Регрессия: разбор URL/имён без небезопасных подстроков (CodeQL)."""

from web.util import _extract_common_for_hierarchy, infer_metadata_source_fields


class TestInferMetadataSourceFields:
    def test_wikipedia_by_hostname(self):
        src, url = infer_metadata_source_fields(
            'Turdus merula',
            'https://upload.wikimedia.org/wikipedia/commons/x.jpg',
            None,
        )
        assert src == 'wikipedia'
        assert 'wikipedia.org' in (url or '')

    def test_inaturalist_host(self):
        src, url = infer_metadata_source_fields(
            None,
            'https://www.inaturalist.org/observations/1',
            None,
        )
        assert src == 'inaturalist'
        assert 'inaturalist.org' in (url or '')

    def test_inaturalist_open_data_bucket(self):
        src, _ = infer_metadata_source_fields(
            None,
            'https://inaturalist-open-data.s3.amazonaws.com/photo.jpg',
            None,
        )
        assert src == 'inaturalist'

    def test_unknown_host_no_substring_bypass(self):
        src, orig = infer_metadata_source_fields(
            None,
            'https://evil-example.net/inaturalist.org',
            None,
        )
        assert src is None
        assert orig is None


class TestExtractCommonForHierarchy:
    def test_parentheses(self):
        assert _extract_common_for_hierarchy('X (Northern Cardinal)') == (
            'Northern Cardinal'
        )
        assert _extract_common_for_hierarchy('Plain') == 'Plain'
        assert _extract_common_for_hierarchy(
            'Bald Eagle (Adult, subadult)',
        ) == 'Adult, subadult'
