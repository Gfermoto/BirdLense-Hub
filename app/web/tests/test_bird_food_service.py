"""Юнит-тесты services.bird_food_service (#293)."""
from models import BirdFood, db
from services.bird_food_service import (
    create_bird_food_from_payload,
    list_bird_food_for_api,
    toggle_bird_food_active,
)


def test_create_then_list(app):
    with app.app_context():
        body, code = create_bird_food_from_payload(
            {'name': f'Svc Oats {id(app)}', 'active': True},
        )
        assert code == 201
        lst = list_bird_food_for_api()
        names = {x['name'] for x in lst}
        assert f'Svc Oats {id(app)}' in names
        bf = BirdFood.query.filter_by(name=f'Svc Oats {id(app)}').first()
        db.session.delete(bf)
        db.session.commit()


def test_create_duplicate_400(app):
    n = f'DupSvc {id(app)}'
    with app.app_context():
        assert create_bird_food_from_payload({'name': n})[1] == 201
        body, code = create_bird_food_from_payload({'name': n})
        assert code == 400
        assert 'error' in body
        bf = BirdFood.query.filter_by(name=n).first()
        db.session.delete(bf)
        db.session.commit()


def test_toggle_missing_404(app):
    with app.app_context():
        body, code = toggle_bird_food_active(-99999)
        assert code == 404


def test_toggle_flips_active(app):
    n = f'ToggleSvc {id(app)}'
    with app.app_context():
        create_bird_food_from_payload({'name': n, 'active': True})
        bid = BirdFood.query.filter_by(name=n).first().id
        _, c1 = toggle_bird_food_active(bid)
        assert c1 == 200
        assert db.session.get(BirdFood, bid).active is False
        toggle_bird_food_active(bid)
        assert db.session.get(BirdFood, bid).active is True
        db.session.delete(db.session.get(BirdFood, bid))
        db.session.commit()
