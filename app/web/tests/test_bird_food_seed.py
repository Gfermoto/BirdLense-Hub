"""BirdFood default catalog — idempotent merge by name."""

import os


class TestBirdFoodSeed:
    def test_seed_bird_food_idempotent(self, app):
        from models import BirdFood, db
        from seed.seed import seed_bird_food

        with app.app_context():
            BirdFood.query.delete()
            db.session.commit()
            first = seed_bird_food()
            db.session.commit()
            count = BirdFood.query.count()
            assert first == count
            assert first >= 10
            assert seed_bird_food() == 0
            db.session.commit()
            assert BirdFood.query.count() == count

    def test_seed_bird_food_skips_existing_name(self, app):
        from models import BirdFood, db
        from seed.seed import seed_bird_food

        with app.app_context():
            BirdFood.query.delete()
            db.session.commit()
            db.session.add(
                BirdFood(
                    name='Oats (uncooked)',
                    description='pre-existing',
                    image_url='data/images/food/cracked-corn.jpg',
                )
            )
            db.session.commit()
            n = seed_bird_food()
            db.session.commit()
            assert n >= 1
            assert BirdFood.query.filter_by(name='Oats (uncooked)').count() == 1

    def test_seed_bird_food_relative_assets_exist(self, app):
        from models import BirdFood, db
        from seed.seed import seed_bird_food

        with app.app_context():
            BirdFood.query.delete()
            db.session.commit()
            seed_bird_food()
            db.session.commit()

            missing = []
            for food in BirdFood.query.all():
                if not food.image_url or food.image_url.startswith('http'):
                    continue
                rel = food.image_url.lstrip('/')
                abs_path = os.path.join(os.path.dirname(__file__), '..', '..', rel)
                if not os.path.isfile(os.path.abspath(abs_path)):
                    missing.append(food.image_url)

            assert missing == []

    def test_migrate_apple_pieces_image_repairs_missing_or_legacy_path(self, app):
        from models import BirdFood, db
        from seed.seed import _migrate_apple_pieces_image

        with app.app_context():
            BirdFood.query.delete()
            db.session.commit()
            row = BirdFood(
                name='Apple pieces',
                description='legacy row',
                image_url='',
            )
            db.session.add(row)
            db.session.commit()

            assert _migrate_apple_pieces_image() is True
            assert row.image_url == 'data/images/food/apple-pieces.svg'
