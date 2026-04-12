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
                    name="Oats (uncooked)",
                    description="pre-existing",
                    image_url="data/images/food/cracked-corn.jpg",
                )
            )
            db.session.commit()
            n = seed_bird_food()
            db.session.commit()
            assert n >= 1
            assert BirdFood.query.filter_by(name="Oats (uncooked)").count() == 1

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
                if not food.image_url or food.image_url.startswith("http"):
                    continue
                rel = food.image_url.lstrip("/")
                abs_path = os.path.join(os.path.dirname(__file__), "..", "..", rel)
                if not os.path.isfile(os.path.abspath(abs_path)):
                    missing.append(food.image_url)

            assert missing == []

    def test_remove_legacy_apple_pieces_deletes_row_and_association(self, app):
        from models import BirdFood, Video, db, video_bird_food_association

        with app.app_context():
            from datetime import datetime, timezone
            from seed.seed import _remove_legacy_apple_pieces_bird_food

            BirdFood.query.delete()
            Video.query.delete()
            db.session.commit()
            apple = BirdFood(
                name="Apple pieces",
                description="legacy",
                image_url="data/images/food/apple-pieces.svg",
            )
            db.session.add(apple)
            db.session.flush()
            v = Video(
                processor_version="t",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                video_path="x/y.mp4",
            )
            db.session.add(v)
            db.session.flush()
            db.session.execute(
                video_bird_food_association.insert().values(
                    video_id=v.id,
                    birdfood_id=apple.id,
                ),
            )
            db.session.commit()

            assert _remove_legacy_apple_pieces_bird_food() is True
            db.session.commit()
            assert BirdFood.query.filter_by(name="Apple pieces").first() is None
            assert (
                db.session.execute(
                    video_bird_food_association.select().where(
                        video_bird_food_association.c.video_id == v.id,
                    ),
                ).first()
                is None
            )
