"""BirdFood default catalog — idempotent merge by name."""


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
