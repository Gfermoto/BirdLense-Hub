"""API каталога: scientific_name из taxon / mapping (#506)."""

from __future__ import annotations

from models import Species, SpeciesTaxon, db
from services.species_catalog.api import _species_row_dict


def test_species_row_scientific_from_linked_taxon(app):
    with app.app_context():
        taxon = SpeciesTaxon(
            taxon_key="catalog-test-garrulus",
            scientific_name="Garrulus glandarius",
            common_name="Catalog Test Jay Zz506",
            wiki_title="Catalog Test Jay Zz506",
            status="active",
        )
        db.session.add(taxon)
        db.session.flush()
        sp = Species(name="Catalog Test Jay Zz506", taxon_id=taxon.id)
        db.session.add(sp)
        db.session.commit()

        class _Row:
            Species = sp
            count = 0

        row = _species_row_dict(
            _Row(),
            regional_scope_ids=set(),
            mapping={},
            allow_keys=frozenset({"catalog test jay zz506"}),
        )
        assert row["name"] == "Catalog Test Jay Zz506"
        assert row["db_name"] == "Catalog Test Jay Zz506"
        assert row["scientific_name"] == "Garrulus glandarius"


def test_species_row_scientific_from_canonical_mapping(app):
    with app.app_context():
        sp = Species(name="Catalog Mapping Jay Zz506")
        db.session.add(sp)
        db.session.commit()
        mapping = {
            "Garrulus glandarius (Catalog Mapping Jay Zz506)": "Catalog Mapping Jay Zz506",
        }

        class _Row:
            Species = sp
            count = 0

        row = _species_row_dict(
            _Row(),
            regional_scope_ids=set(),
            mapping=mapping,
            allow_keys=frozenset({"catalog mapping jay zz506"}),
        )
        assert row["scientific_name"] == "Garrulus glandarius"
