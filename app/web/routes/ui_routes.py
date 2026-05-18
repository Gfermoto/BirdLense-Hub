"""Регистрация ``/api/ui/*`` (домены — ``ui_*_routes.py``, #198)."""

from routes.ui_timeline_helpers import build_merged_timeline_items
from time_util import parse_timeline_iso

# Обратная совместимость: раньше имя было с подчёркиванием
_parse_timeline_iso = parse_timeline_iso

__all__ = [
    "register_routes",
    "build_merged_timeline_items",
    "parse_timeline_iso",
    "_parse_timeline_iso",
]


def register_routes(app):
    """Основные ``/api/ui/*`` (без system — ``ui_system_routes``)."""
    from routes.ui_birdfood_routes import register_ui_birdfood_routes
    from routes.ui_analytics_routes import register_ui_analytics_routes
    from routes.ui_corrections_dataset_routes import (
        register_ui_corrections_dataset_routes,
    )
    from routes.ui_overview_timeline_routes import (
        register_ui_overview_timeline_routes,
    )
    from routes.ui_ml_ops_routes import register_ui_ml_ops_routes
    from routes.ui_settings_routes import register_ui_settings_routes
    from routes.ui_species_catalog_routes import (
        register_ui_species_catalog_routes,
    )
    from routes.ui_species_media_routes import (
        register_ui_species_media_routes,
    )
    from routes.ui_status_push_routes import register_ui_status_push_routes
    from routes.ui_video_routes import register_ui_video_routes

    register_ui_status_push_routes(app)
    register_ui_birdfood_routes(app)
    register_ui_analytics_routes(app)
    register_ui_video_routes(app)
    register_ui_overview_timeline_routes(app)
    register_ui_ml_ops_routes(app)
    register_ui_corrections_dataset_routes(app)
    register_ui_species_catalog_routes(app)
    register_ui_settings_routes(app)
    register_ui_species_media_routes(app)
