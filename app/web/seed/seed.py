import logging
import os

from sqlalchemy import delete, func

from models import Species, BirdFood, db, video_bird_food_association
from util import build_hierarchy_tree

# Default BirdFood catalog (Settings / feeder). Curated by maintainers from common EU + US practice.
# Image paths are under data/images/food/ (served as static paths in the app).
# On each startup, `seed()` merges any missing rows by unique `name` (existing installs get new items).


def dfs_traverse_and_insert(tree, parent_id=None):
    """
    Perform DFS traversal and insert records into the database.
    """
    for node_id, children in tree.items():
        # Create and insert the species record
        # Adjust name if necessary
        species = Species(name=node_id, parent_id=parent_id)
        db.session.add(species)
        db.session.flush()  # Flush to get the id without committing

        # Recursively insert children
        dfs_traverse_and_insert(children, species.id)


def seed_bird_food() -> int:
    """Insert catalog BirdFood rows missing by `name`. Returns count inserted."""
    foods = [
        {
            'name': 'Black-oil Sunflower Seeds',
            'description': 'High in energy with thin shells. Preferred food for cardinals, chickadees, finches, sparrows, and occasionally woodpeckers.',
            'image_url': 'data/images/food/black-oil-sunflower-seeds.jpg',
        },
        {
            'name': 'Cracked Corn',
            'description': 'Inexpensive grain attractive to doves, quail, and sparrows. Best mixed with millet.',
            'image_url': 'data/images/food/cracked-corn.jpg',
        },
        {
            'name': 'Fruit',
            'description': 'Attracts orioles, mockingbirds, catbirds, bluebirds, robins, and waxwings. Includes oranges, grapes, raisins.',
            'image_url': "data/images/food/fruit.jpg",
        },
        {
            'name': 'Hulled Sunflower Seeds',
            'description': '"No mess" sunflower without shells. Preferred by many birds but spoils quickly if wet.',
            'image_url': "data/images/food/hulled-sunflower-seeds.jpg",
        },
        {
            'name': 'Mealworms',
            'description': 'High protein larvae attracting chickadees, titmice, wrens, nuthatches, and especially bluebirds.',
            'image_url': "data/images/food/mealworms.jpg",
        },
        {
            'name': 'Millet',
            'description': 'Small, round grain favored by ground foraging birds like juncos and sparrows.',
            'image_url': "data/images/food/millets.jpg"
        },
        {
            'name': 'Nyjer',
            'description': 'Small, oil-rich niger/thistle-type seed for specialist finches — e.g. American Goldfinch, European Goldfinch, Pine Siskin, Common Redpoll.',
            'image_url': 'data/images/food/nyjer.jpg',
        },
        {
            'name': 'Peanuts',
            'description': 'Popular with jays, chickadees, nuthatches, and titmice. Can be offered shelled or unshelled.',
            'image_url': 'data/images/food/peanuts.jpg',
        },
        {
            'name': 'Safflower',
            'description': 'White sunflower-like seed attracting cardinals and other big-billed birds.',
            'image_url': "data/images/food/safflower.jpg",
        },
        {
            'name': 'Suet',
            'description': 'Beef kidney fat attractive to insect-eating birds. Available plain or in processed cakes with seeds.',
            'image_url': 'data/images/food/suet.jpg',
        },
        # Europe-focused additions (reuse bundled images where no separate asset exists)
        {
            'name': 'Fat balls (suet cakes)',
            'description': 'Very common in European gardens: fat mixed with seeds or insects for tits, woodpeckers, robins, and blackbirds in cold weather.',
            'image_url': 'data/images/food/suet.jpg',
        },
        {
            'name': 'Hemp seed',
            'description': 'Small oily seed for finches, siskins, and buntings. Use **hemp sold for bird feeding** (legal bird-food grade in the EU).',
            'image_url': 'data/images/food/millets.jpg',
        },
        {
            'name': 'Oats (uncooked)',
            'description': 'Plain rolled/porridge oats for blackbirds, chaffinches, sparrows, and corvids. Avoid flavored or instant oats.',
            'image_url': 'data/images/food/cracked-corn.jpg',
        },
        {
            'name': 'Mixed wild bird seed',
            'description': 'Typical shop blends (wheat, barley, millet, small seeds) for ground and table feeding — widely used across Europe.',
            'image_url': 'data/images/food/millets.jpg',
        },
        {
            'name': 'Rapeseed (canola)',
            'description': 'Small dark seed often included in EU mixes; attracts finches and buntings when offered dry in feeders.',
            'image_url': 'data/images/food/millets.jpg',
        },
    ]

    existing = {row[0] for row in BirdFood.query.with_entities(BirdFood.name).all()}
    added = 0
    for food_data in foods:
        if food_data['name'] in existing:
            continue
        db.session.add(BirdFood(**food_data))
        existing.add(food_data['name'])
        added += 1
    return added


def _food_asset_exists(image_url: str | None) -> bool:
    if not image_url or not isinstance(image_url, str):
        return False
    if image_url.startswith('http://') or image_url.startswith('https://'):
        return True
    rel = image_url.lstrip('/')
    base_dir = os.path.join(os.path.dirname(__file__), '..', '..')
    return os.path.isfile(os.path.abspath(os.path.join(base_dir, rel)))


def _remove_legacy_apple_pieces_bird_food() -> bool:
    """Убрать позицию «Apple pieces» из каталога корма (в т.ч. старые БД)."""
    rows = BirdFood.query.filter(
        func.lower(func.trim(BirdFood.name)) == 'apple pieces',
    ).all()
    if not rows:
        return False
    for row in rows:
        fid = row.id
        db.session.execute(
            delete(video_bird_food_association).where(
                video_bird_food_association.c.birdfood_id == fid,
            ),
        )
        db.session.delete(row)
    return True


def seed():
    if not Species.query.first():
        logging.info('Seeding species hierarchy data...')
        tree = build_hierarchy_tree()
        dfs_traverse_and_insert(tree)
        db.session.commit()
        logging.info('Species seeding complete.')

    n_food = seed_bird_food()
    removed_apple = _remove_legacy_apple_pieces_bird_food()
    if n_food or removed_apple:
        if n_food:
            logging.info('Bird food catalog: added %s new default row(s)', n_food)
        if removed_apple:
            logging.info('Bird food: removed legacy «Apple pieces» row(s)')
        db.session.commit()
    elif not BirdFood.query.first():
        logging.warning('Bird food catalog empty and nothing inserted — check seed_bird_food()')
