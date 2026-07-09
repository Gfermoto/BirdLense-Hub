"""Species catalog missing_audio filter (#509)."""

from __future__ import annotations

from services.species_catalog.api import _species_has_catalog_audio


class _Sp:
    def __init__(self, source=None, url=None):
        self.metadata_source = source
        self.metadata_source_url = url


def test_species_has_catalog_audio_xeno_url():
    sp = _Sp(url="https://xeno-canto.org/explore?query=parus")
    assert _species_has_catalog_audio(sp) is True


def test_species_has_catalog_audio_negative():
    sp = _Sp(source="inaturalist", url="https://inaturalist.org/1")
    assert _species_has_catalog_audio(sp) is False
