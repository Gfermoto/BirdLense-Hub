"""Парсинг JSON-тела запроса и единый формат 400 для mutating API (#281).

Эндпоинты с ``parse_request_json_dict`` / ``validation_error`` (расширяем по мере работы):

- ``POST /api/ui/birdfood`` — только JSON-object; поля проверяются в ``bird_food_service``.
- ``POST /api/ui/storage/purge`` — только JSON-object; даты — строки ``YYYY-MM-DD`` в ``purge_storage_from_body``.

Ответ **400** при ошибке схемы: ``{"error": "<кратко>", "fields": {"<поле>": ["<причина>", ...]}}``.
"""

from __future__ import annotations

from typing import Any

from flask import Request


def validation_error(message: str, fields: dict[str, list[str]]) -> dict[str, Any]:
    """Тело ответа при ошибке схемы: короткий ``error`` + детали по полям."""
    return {"error": message, "fields": fields}


def parse_request_json_dict(request: Request) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Ожидается непустое тело с JSON-объектом (dict).
    Успех: ``(data, None)``. Ошибка: ``(None, error_body)`` — отдавать с кодом **400**.
    """
    raw = request.get_json(silent=True)
    if raw is None:
        text = (request.get_data(as_text=True) or "").strip()
        if not text:
            return None, validation_error(
                "JSON body required",
                {"_body": ["body is empty or not JSON"]},
            )
        return None, validation_error(
            "Invalid JSON",
            {"_body": ["could not parse JSON"]},
        )
    if not isinstance(raw, dict):
        return None, validation_error(
            "JSON body must be an object",
            {"_body": ["expected a JSON object, not an array or primitive"]},
        )
    return raw, None
