#!/usr/bin/env python3
"""
Объединение дубликатов видов в БД.

Варианты имён (Garrulus glandarius (Eurasian Jay), Eurasian Jay и т.д.)
сливаются в канонический вид (Eurasian Jay — Common name).

Использует app/web/seed/species_canonical_mapping.txt.
Запуск: cd app && python -m scripts.merge_duplicate_species
       или: cd app && python ../scripts/merge_duplicate_species.py
"""
import os
import sys

# Add project root and app to path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_app_dir = os.path.join(_project_root, 'app')
for p in (_app_dir, _project_root):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(_app_dir)

def main():
    from web.util import load_species_canonical_mapping
    from web.models import db, Species, VideoSpecies, SpeciesVisit
    from web.app import create_app

    app = create_app()
    with app.app_context():
        mapping = load_species_canonical_mapping()
        if not mapping:
            print("No species_canonical_mapping.txt or empty. Nothing to do.")
            return

        # Build canonical -> [variants]
        canonical_to_variants = {}
        for variant, canonical in mapping.items():
            canonical_to_variants.setdefault(canonical, []).append(variant)

        merged = 0
        for canonical, variants in canonical_to_variants.items():
            # Find all Species with these names
            species_list = Species.query.filter(Species.name.in_(variants)).all()
            if len(species_list) <= 1:
                continue

            # Prefer Species with name == canonical as target
            target = next((s for s in species_list if s.name == canonical), species_list[0])
            others = [s for s in species_list if s.id != target.id]

            for other in others:
                # Update VideoSpecies
                updated_vs = VideoSpecies.query.filter_by(species_id=other.id).update(
                    {'species_id': target.id}
                )
                # Update SpeciesVisit
                updated_sv = SpeciesVisit.query.filter_by(species_id=other.id).update(
                    {'species_id': target.id}
                )
                # Update children parent_id
                Species.query.filter_by(parent_id=other.id).update({'parent_id': target.id})
                # Ensure target has canonical name
                if target.name != canonical:
                    target.name = canonical
                db.session.delete(other)
                merged += 1
                print(f"  Merged '{other.name}' -> '{canonical}' (VideoSpecies: {updated_vs}, SpeciesVisit: {updated_sv})")

        if merged:
            db.session.commit()
            print(f"Done. Merged {merged} duplicate species.")
        else:
            print("No duplicates found.")

if __name__ == '__main__':
    main()
