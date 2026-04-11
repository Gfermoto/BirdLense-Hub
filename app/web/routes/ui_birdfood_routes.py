"""CRUD BirdFood для UI (#198)."""

from flask import request

from auth import settings_check_access
from services.bird_food_service import (
    create_bird_food_from_payload,
    list_bird_food_for_api,
    toggle_bird_food_active,
)


def register_ui_birdfood_routes(app):
    """Зарегистрировать маршруты /api/ui/birdfood."""
    @app.route('/api/ui/birdfood', methods=['POST'])
    def add_birdfood():
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        body, status = create_bird_food_from_payload(request.json)
        return body, status

    @app.route('/api/ui/birdfood/<int:birdfood_id>/toggle', methods=['PATCH'])
    def toggle_birdfood(birdfood_id):
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        body, status = toggle_bird_food_active(birdfood_id)
        return body, status

    @app.route('/api/ui/birdfood', methods=['GET'])
    def get_birdfood():
        return list_bird_food_for_api(), 200
