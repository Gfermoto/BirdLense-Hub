"""BirdFood CRUD для UI API (#293)."""

from __future__ import annotations

from typing import Any

from models import BirdFood, db


def list_bird_food_for_api() -> list[dict[str, Any]]:
    rows = BirdFood.query.order_by(BirdFood.name.asc()).all()
    return [
        {
            "id": food.id,
            "name": food.name,
            "active": food.active,
            "description": food.description,
            "image_url": food.image_url,
        }
        for food in rows
    ]


def create_bird_food_from_payload(data: dict | None) -> tuple[dict, int]:
    """POST body → (response_body, http_status)."""
    if not data:
        return {"error": "Name is required"}, 400
    name = data.get("name")
    if name is None or (isinstance(name, str) and not name.strip()):
        return {"error": "Name is required"}, 400
    name_s = name.strip() if isinstance(name, str) else str(name).strip()
    if BirdFood.query.filter_by(name=name_s).first():
        return {"error": "Bird food with this name already exists"}, 400
    row = BirdFood(name=name_s, active=data.get("active", True))
    db.session.add(row)
    db.session.commit()
    return {"message": "Bird food added successfully"}, 201


def toggle_bird_food_active(birdfood_id: int) -> tuple[dict, int]:
    row = db.session.get(BirdFood, birdfood_id)
    if not row:
        return {"error": "Bird food not found"}, 404
    row.active = not row.active
    db.session.commit()
    return {"message": "Bird food active status toggled successfully"}, 200
