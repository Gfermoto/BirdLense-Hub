"""Scan recordings, visits maintenance, species merge/reconcile (#265)."""

from __future__ import annotations

from flask import request

from routes.http_guards import require_ui_settings_password
from services.api_json_validation import parse_request_json_object_allow_empty
from services.reconcile_recordings_service import run_disk_db_reconcile
from services.system_maintenance_service import (
    post_clean_orphaned_visits,
    post_merge_duplicate_species,
    post_realign_visit_times,
    post_species_catalog_deep_reconcile,
    post_species_catalog_reconcile,
    post_split_large_gap_visits,
    run_recordings_scan,
)


def register_ui_system_maintenance_routes(app):
    """Импорт с диска и обслуживание видов/визитов."""

    @app.route("/api/ui/system/recordings/scan", methods=["POST"])
    @require_ui_settings_password
    def scan_recordings():
        """
        Scan data/recordings/ for video.mp4 not in DB and add them.
        Fixes recordings missing from stats after server restart.
        """
        body, code = run_recordings_scan(app)
        return body, code

    @app.route("/api/ui/system/recordings/reconcile", methods=["POST"])
    @require_ui_settings_password
    def reconcile_recordings():
        """Disk↔DB reconcile: import orphans, purge stale disk/DB per policy (#604)."""
        body = run_disk_db_reconcile(app)
        code = 200 if body.get("ok", True) else 500
        return body, code

    @app.route("/api/ui/system/clean-orphaned-visits", methods=["POST"])
    @require_ui_settings_password
    def clean_orphaned_visits():
        """
        Удалить осиротевшие SpeciesVisit (без VideoSpecies) и синхронизировать
        VideoSpecies.species_id с visit.species_id. Исправляет некорректные счётчики
        в календаре миграций и каталоге после старых коррекций.
        """
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        body, code = post_clean_orphaned_visits(payload)
        return body, code

    @app.route("/api/ui/system/realign-visit-times", methods=["POST"])
    @require_ui_settings_password
    def realign_visit_times():
        """Preview/apply SpeciesVisit time realignment from actual detection timestamps."""
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        body, code = post_realign_visit_times(payload)
        return body, code

    @app.route("/api/ui/system/split-large-gap-visits", methods=["POST"])
    @require_ui_settings_password
    def split_large_gap_visits():
        """Preview/apply splitting of visits with large internal detection gaps."""
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        body, code = post_split_large_gap_visits(payload)
        return body, code

    @app.route("/api/ui/system/merge-duplicate-species", methods=["POST"])
    @require_ui_settings_password
    def merge_duplicate_species():
        """
        Объединить дубликаты видов (Garrulus glandarius (Eurasian Jay) -> Eurasian Jay).
        Использует species_canonical_mapping.txt. Сопоставление без учёта регистра.
        """
        body, code = post_merge_duplicate_species()
        return body, code

    @app.route("/api/ui/system/species-catalog/reconcile", methods=["POST"])
    @require_ui_settings_password
    def species_catalog_reconcile():
        """
        Привести каталог видов: слияние дубликатов по нормализованному имени;
        опционально перенос подозрительных (блоклист) и строк вне allowlist на «Unknown».

        body JSON:
          dry_run (default true),
          merge_normalized_duplicate_names (default true),
          reassign_suspects_to_unknown, delete_empty_suspects,
          reassign_off_allowlist_to_unknown, delete_empty_off_allowlist,
          duplicate_group_limit (default 500).

        Allowlist: species.catalog_allowlist_file → scripts/datasets/dump_classifier_allowlist.py
        """
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        body, code = post_species_catalog_reconcile(payload)
        return body, code

    @app.route("/api/ui/system/species-catalog/deep-reconcile", methods=["POST"])
    @require_ui_settings_password
    def species_catalog_deep_reconcile():
        """
        Глубокий reconcile каталога: merge дубликатов + канонизация display names.

        body JSON: dry_run (default true), duplicate_group_limit, rename_limit.
        """
        payload, v_err = parse_request_json_object_allow_empty(request)
        if v_err is not None:
            return v_err, 400
        body, code = post_species_catalog_deep_reconcile(payload)
        return body, code
