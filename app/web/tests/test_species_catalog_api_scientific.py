"""API каталога: scientific_name из taxon / mapping (#506)."""

from __future__ import annotations

from models import Species, SpeciesTaxon, db
from services.species_catalog.api import _species_row_dict, fetch_species_catalog_list


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


def test_project_catalog_includes_bird_and_repairs_rodent(app):
    with app.app_context():
        birds = Species.query.filter_by(name="Birds").first()
        if birds is None:
            birds = Species(name="Birds")
            db.session.add(birds)
            db.session.flush()
        bird = Species.query.filter_by(name="Bird").first()
        if bird is None:
            bird = Species(name="Bird", active=True, parent=birds)
            db.session.add(bird)
        rodent = Species.query.filter_by(name="Rodent").first()
        if rodent is None:
            rodent = Species(name="Rodent")
            db.session.add(rodent)
        rodent.active = False
        rodent.parent_id = None
        rodent.description = None
        db.session.commit()

        rows = fetch_species_catalog_list(db.session, exclude_suspects=True, scope="project")
        by_name = {row["name"]: row for row in rows}

        assert by_name["Bird"]["active"] is True
        assert by_name["Bird"]["parent_id"] == birds.id
        assert by_name["Bird"]["description"]
        assert by_name["Rodent"]["active"] is True
        assert by_name["Rodent"]["parent_id"] == birds.id
        assert by_name["Rodent"]["description"]
