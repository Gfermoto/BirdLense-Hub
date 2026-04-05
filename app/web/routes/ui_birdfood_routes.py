"""CRUD BirdFood для UI (#198)."""

from flask import request

from auth import settings_check_access
from models import BirdFood, db


def register_ui_birdfood_routes(app):
    @app.route('/api/ui/birdfood', methods=['POST'])
    def add_birdfood():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        data = request.json
        name = data.get('name')
        if not name:
            return {'error': 'Name is required'}, 400

        bird_food = BirdFood.query.filter_by(name=name).first()
        if bird_food:
            return {'error': 'Bird food with this name already exists'}, 400

        bird_food = BirdFood(name=name, active=data.get('active', True))
        db.session.add(bird_food)
        db.session.commit()

        return {'message': 'Bird food added successfully'}, 201

    @app.route('/api/ui/birdfood/<int:birdfood_id>/toggle', methods=['PATCH'])
    def toggle_birdfood(birdfood_id):
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        bird_food = db.session.get(BirdFood, birdfood_id)
        if not bird_food:
            return {'error': 'Bird food not found'}, 404

        bird_food.active = not bird_food.active
        db.session.commit()

        return {'message': 'Bird food active status toggled successfully'}, 200

    @app.route('/api/ui/birdfood', methods=['GET'])
    def get_birdfood():
        bird_food = BirdFood.query.order_by(BirdFood.name.asc()).all()
        bird_food_list = [{
            'id': food.id,
            'name': food.name,
            'active': food.active,
            'description': food.description,
            'image_url': food.image_url,
        } for food in bird_food]

        return bird_food_list, 200
