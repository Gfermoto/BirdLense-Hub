"""Idealize catalog: collision merge, empty hierarchy purge."""

from __future__ import annotations

from models import Species, db
from services.species_catalog.idealize import (
    merge_canonical_name_collisions,
    purge_empty_hierarchy_nodes,
)


def test_merge_canonical_name_collisions_merges_legacy_scientific_form(app, monkeypatch):
    with app.app_context():
        target = Species(name="Catalog Ideal Robin Zz506")
        legacy = Species(name="Erithacus rubecula (Catalog Ideal Robin Zz506)")
        db.session.add_all([target, legacy])
        db.session.commit()
        tid, lid = target.id, legacy.id
        monkeypatch.setattr(
            "services.species_catalog.idealize.load_catalog_allowlist_norm_keys",
            lambda *_a, **_k: frozenset({"catalog ideal robin zz506"}),
        )
        monkeypatch.setattr(
            "services.species_catalog.idealize.normalize_catalog_display_name",
            lambda value, _mapping: "Catalog Ideal Robin Zz506" if "robin zz506" in str(value).lower() else value,
        )
        out = merge_canonical_name_collisions(dry_run=False)
        assert out["merged"] >= 1
        assert db.session.get(Species, lid) is None
        assert db.session.get(Species, tid) is not None


def test_purge_empty_hierarchy_deletes_orphan_group(app, monkeypatch):
    with app.app_context():
        group = Species(name="Test Group And Allies Zz506")
        db.session.add(group)
        db.session.commit()
        gid = group.id
        monkeypatch.setattr(
            "services.species_catalog.idealize.is_hierarchy_taxon_label",
            lambda name, **_k: "and allies" in str(name).lower(),
        )
        monkeypatch.setattr(
            "services.species_catalog.idealize.load_catalog_allowlist_norm_keys",
            lambda *_a, **_k: frozenset(),
        )
        out = purge_empty_hierarchy_nodes(dry_run=False)
        assert out["deleted"] >= 1
        assert db.session.get(Species, gid) is None
