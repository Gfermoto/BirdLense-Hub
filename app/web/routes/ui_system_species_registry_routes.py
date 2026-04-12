"""Species registry admin API under /api/ui/system/species-registry/ (#223)."""

from __future__ import annotations

from flask import request

from routes.http_guards import require_ui_settings_password
from services.species_registry_admin_service import (
    catalog_coverage_metrics_body,
    classifier_dataset_alignment_report,
    export_tuning_targets,
    get_species_registry_health_body,
    get_unresolved_species_report,
    materialize_allowlist_species,
    normalize_export_format,
    parse_unresolved_limit,
    repair_catalog_cards_status_snapshot,
    run_species_registry_backfill,
    seed_species_registry,
    species_data_quality_report,
    species_metadata_enrichment_status_body,
    start_metadata_enrichment,
    start_repair_catalog_cards,
)


def register_ui_system_species_registry_routes(app):
    """Register `/api/ui/system/species-registry/*` admin routes."""

    @app.route("/api/ui/system/species-registry/seed", methods=["POST"])
    @require_ui_settings_password
    def seed_species_registry_route():
        """Seed canonical species registry and aliases from mapping file."""
        body, code = seed_species_registry()
        return body, code

    @app.route("/api/ui/system/species-registry/backfill", methods=["POST"])
    @require_ui_settings_password
    def run_species_registry_backfill_route():
        """Backfill existing Species rows with canonical taxon links.

        body: {"dry_run": true|false, "limit": 500}
        """
        payload = request.get_json(silent=True) or {}
        body, code = run_species_registry_backfill(payload)
        return body, code

    @app.route("/api/ui/system/species-registry/unresolved", methods=["GET"])
    @require_ui_settings_password
    def get_unresolved_species_names():
        """Top unresolved species names captured by resolver."""
        limit = parse_unresolved_limit(request.args.get("limit"))
        body, code = get_unresolved_species_report(limit)
        return body, code

    @app.route(
        "/api/ui/system/species-registry/enrich-metadata/start",
        methods=["POST"],
    )
    @require_ui_settings_password
    def start_species_registry_metadata_enrichment():
        """Start async enrichment batch.

        body: {"limit": 300, "retry_failed_only": false}
        """
        payload = request.get_json(silent=True) or {}
        body, code = start_metadata_enrichment(app, payload)
        return body, code

    @app.route(
        "/api/ui/system/species-registry/enrich-metadata/status",
        methods=["GET"],
    )
    @require_ui_settings_password
    def species_registry_metadata_enrichment_status():
        """Get async enrichment status."""
        return species_metadata_enrichment_status_body(), 200

    @app.route("/api/ui/system/species-registry/health", methods=["GET"])
    @require_ui_settings_password
    def get_species_registry_health():
        """Registry rollout health metrics."""
        body, code = get_species_registry_health_body()
        return body, code

    @app.route(
        "/api/ui/system/species-registry/materialize-allowlist",
        methods=["POST"],
    )
    @require_ui_settings_password
    def species_registry_materialize_allowlist():
        """Create missing Species rows for allowlist; optional metadata fill."""
        payload = request.get_json(silent=True) or {}
        body, code = materialize_allowlist_species(payload)
        return body, code

    @app.route(
        "/api/ui/system/species-registry/repair-cards/start",
        methods=["POST"],
    )
    @require_ui_settings_password
    def species_registry_repair_cards_start():
        """Start background repair for species cards."""
        payload = request.get_json(silent=True) or {}
        body, code = start_repair_catalog_cards(app, payload)
        return body, code

    @app.route(
        "/api/ui/system/species-registry/repair-cards/status",
        methods=["GET"],
    )
    @require_ui_settings_password
    def species_registry_repair_cards_status():
        """Read background repair status with live coverage counters."""
        return repair_catalog_cards_status_snapshot(), 200

    @app.route("/api/ui/system/species-registry/data-quality", methods=["GET"])
    @require_ui_settings_password
    def species_registry_data_quality():
        """Отчёт: мусор в каталоге, дубликаты имён (слияние)."""
        dup_limit = request.args.get("duplicate_limit", type=int) or 80
        body, code = species_data_quality_report(dup_limit)
        return body, code

    @app.route(
        "/api/ui/system/species-registry/classifier-dataset-alignment",
        methods=["GET"],
    )
    @require_ui_settings_password
    def species_registry_classifier_dataset_alignment():
        """Classifier classes vs Species catalog vs dataset folders."""
        clf_lim = request.args.get("classifier_limit", type=int) or 600
        cat_lim = request.args.get("catalog_limit", type=int) or 400
        ds_lim = request.args.get("dataset_limit", type=int) or 200
        body, code = classifier_dataset_alignment_report(
            clf_lim,
            cat_lim,
            ds_lim,
        )
        return body, code

    @app.route(
        "/api/ui/system/species-registry/coverage-metrics",
        methods=["GET"],
    )
    @require_ui_settings_password
    def species_registry_coverage_metrics():
        """Coverage: observed / dataset / full EU catalog segments."""
        body, code = catalog_coverage_metrics_body()
        return body, code

    @app.route(
        "/api/ui/system/species-registry/tuning-targets/export",
        methods=["GET"],
    )
    @require_ui_settings_password
    def species_registry_tuning_targets_export():
        """Export manually marked tuning targets for training pipeline."""
        fmt = normalize_export_format(request.args.get("format"))
        body, code = export_tuning_targets(fmt)
        return body, code
