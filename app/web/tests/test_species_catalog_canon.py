"""Unit tests for species catalog canon layer."""

from services.species_catalog.canon import (
    audio_search_term_for_species_name,
    is_hierarchy_taxon_label,
    normalize_catalog_display_name,
)


def test_normalize_catalog_display_name_title_cases_all_caps(monkeypatch):
    monkeypatch.setattr(
        "services.species_catalog.canon.load_species_canonical_mapping",
        lambda: {"great tit": "Great Tit"},
    )
    monkeypatch.setattr(
        "services.species_catalog.canon.normalize_species_to_canonical",
        lambda value, _mapping: "Great Tit" if str(value).upper() == "GREAT TIT" else value,
    )
    assert normalize_catalog_display_name("GREAT TIT") == "Great Tit"


def test_is_hierarchy_taxon_label_detects_group_names():
    assert is_hierarchy_taxon_label("Starlings and Allies", allowlist_norm_keys=frozenset())
    assert is_hierarchy_taxon_label("Ducks, Geese, and Swans", allowlist_norm_keys=frozenset())


def test_is_hierarchy_taxon_label_allows_allowlist_species(monkeypatch):
    allow = frozenset({"common starling"})

    def _matches(name, keys, _mapping):
        return str(name).strip().lower() in keys

    monkeypatch.setattr(
        "services.species_catalog.allowlist.species_matches_allowlist",
        _matches,
    )
    assert not is_hierarchy_taxon_label(
        "Common Starling",
        allowlist_norm_keys=allow,
        mapping={},
    )


def test_audio_search_term_for_group_uses_allowlist_child(monkeypatch):
    allow = frozenset({"common starling"})
    def _matches(name, allow, _mapping):
        from services.species_catalog.canon import parse_scientific_and_common

        variants = {_norm(name)}
        _sci, common = parse_scientific_and_common(str(name))
        if common:
            variants.add(_norm(common))
        return bool(variants & allow)

    def _norm(s):
        return str(s).strip().lower()

    monkeypatch.setattr(
        "services.species_catalog.allowlist.species_matches_allowlist",
        _matches,
    )
    monkeypatch.setattr(
        "services.species_catalog.canon.load_hierarchy_parent_child_map",
        lambda: {"Starlings and Allies": ["Sturnus vulgaris (Common Starling)"]},
    )
    monkeypatch.setattr(
        "services.species_catalog.canon.normalize_catalog_display_name",
        lambda value, _mapping: value,
    )
    term = audio_search_term_for_species_name(
        "Starlings and Allies",
        allowlist_norm_keys=allow,
        mapping={},
    )
    assert term == "Common Starling"
