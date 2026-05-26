"""Регистрация всех HTTP-маршрутов Hub (единая точка вызова из create_app, #292)."""

from __future__ import annotations

from flask import Flask

from . import processor_routes, ui_routes, ui_system_routes
from .debug_bbox_parity_routes import register_debug_bbox_parity_routes
from .debug_scoring_routes import register_debug_scoring_routes
from .debug_bbox_parity_routes import register_debug_bbox_parity_routes


def register_all_routes(app: Flask) -> None:
    ui_routes.register_routes(app)
    ui_system_routes.register_routes(app)
    processor_routes.register_routes(app)
    register_debug_scoring_routes(app)
    register_debug_bbox_parity_routes(app)
