"""BirdFood CRUD для UI API (#293)."""

from __future__ import annotations

from typing import Any

from models import BirdFood, db
from services.api_json_validation import validation_error


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


def create_bird_food_from_payload(data: dict) -> tuple[dict, int]:
    """POST body → (response_body, http_status). ``data`` — JSON-объект (после parse)."""
    fields: dict[str, list[str]] = {}
    name = data.get("name")
    if name is None:
        fields.setdefault("name", []).append("required")
    elif not isinstance(name, str):
        fields.setdefault("name", []).append("must be a non-empty string")
    elif not name.strip():
        fields.setdefault("name", []).append("required")

    if "active" in data and not isinstance(data["active"], bool):
        fields.setdefault("active", []).append("must be boolean")

    if fields:
        return validation_error("Validation failed", fields), 400

    name_s = name.strip()  # type: ignore[union-attr]
    if BirdFood.query.filter_by(name=name_s).first():
        return validation_error(
            "Bird food with this name already exists",
            {"name": ["already exists"]},
        ), 400
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
