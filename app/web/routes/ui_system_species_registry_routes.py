"""Species registry admin API under /api/ui/system/species-registry/ (#223)."""

import csv
import io
import threading

from flask import Response, request

from app_config.app_config import app_config
from models import Species, db
from services.http_response_cache import (
    bust_response_caches,
    bust_system_response_caches,
)
from services.species_registry_service import (
    backfill_species_taxa,
    catalog_cards_coverage_snapshot,
    ensure_allowlist_species_materialized,
    ensure_species_registry_seeded,
    enrich_species_metadata_with_status,
    repair_catalog_cards,
    species_registry_health,
    unresolved_species_report,
)
from util import settings_check_access

from routes import ui_system_routes as uis


def register_ui_system_species_registry_routes(app):
    """Register `/api/ui/system/species-registry/*` admin routes."""

    @app.route('/api/ui/system/species-registry/seed', methods=['POST'])
    def seed_species_registry():
        """Seed canonical species registry and aliases from mapping file."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            stats = ensure_species_registry_seeded()
            bust_response_caches()
            bust_system_response_caches()
            return {'ok': True, **stats}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Seed species registry failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/backfill', methods=['POST'])
    def run_species_registry_backfill():
        """Backfill existing Species rows with canonical taxon links.

        body: {"dry_run": true|false, "limit": 500}
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            limit = payload.get('limit')
            if limit is not None:
                try:
                    limit = int(limit)
                except (ValueError, TypeError):
                    return {'error': 'limit must be int'}, 400
            stats = backfill_species_taxa(dry_run=dry_run, limit=limit)
            if not dry_run:
                bust_response_caches()
                bust_system_response_caches()
            return {'ok': True, **stats}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Species registry backfill failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-registry/unresolved', methods=['GET'])
    def get_unresolved_species_names():
        """Top unresolved species names captured by resolver."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            raw_limit = request.args.get('limit', 100)
            try:
                limit = int(raw_limit)
            except (ValueError, TypeError):
                limit = 100
            items = unresolved_species_report(limit=limit)
            return {'items': items, 'count': len(items)}, 200
        except Exception as e:
            app.logger.exception('Unresolved species report failed: %s', e)
            return {'error': str(e)}, 500

    @app.route(
        '/api/ui/system/species-registry/enrich-metadata/start',
        methods=['POST'],
    )
    def start_species_registry_metadata_enrichment():
        """Start async enrichment batch.

        body: {"limit": 300, "retry_failed_only": false}
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with uis._species_metadata_lock:
            if uis._species_metadata_status.get('status') == 'running':
                return {
                    'error': 'Enrichment already running',
                    'status': uis._species_metadata_status,
                }, 409
            payload = request.get_json(silent=True) or {}
            try:
                limit = int(payload.get('limit', 300))
            except (ValueError, TypeError):
                return {'error': 'limit must be int'}, 400
            retry_failed_only = bool(payload.get('retry_failed_only', False))
            uis._species_metadata_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': {
                    'limit': limit,
                    'retry_failed_only': retry_failed_only,
                },
            })

            def _run():
                try:
                    with app.app_context():
                        stats = enrich_species_metadata_with_status(
                            limit=limit,
                            dry_run=False,
                            retry_failed_only=retry_failed_only,
                        )
                    with uis._species_metadata_lock:
                        uis._species_metadata_status.update({
                            'status': 'done',
                            'result': stats,
                            'error': None,
                        })
                except Exception as e:
                    with uis._species_metadata_lock:
                        uis._species_metadata_status.update({
                            'status': 'error',
                            'result': None,
                            'error': str(e),
                        })

            threading.Thread(target=_run, daemon=True).start()
            return {
                'message': 'Species metadata enrichment started',
                'status': uis._species_metadata_status,
            }, 202

    @app.route(
        '/api/ui/system/species-registry/enrich-metadata/status',
        methods=['GET'],
    )
    def species_registry_metadata_enrichment_status():
        """Get async enrichment status."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with uis._species_metadata_lock:
            return dict(uis._species_metadata_status), 200

    @app.route('/api/ui/system/species-registry/health', methods=['GET'])
    def get_species_registry_health():
        """Registry rollout health metrics."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            return species_registry_health(), 200
        except Exception as e:
            app.logger.exception('Species registry health failed: %s', e)
            return {'error': str(e)}, 500

    @app.route(
        '/api/ui/system/species-registry/materialize-allowlist',
        methods=['POST'],
    )
    def species_registry_materialize_allowlist():
        """Create missing Species rows for allowlist; optional metadata fill."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        payload = request.get_json(silent=True) or {}
        dry_run = bool(payload.get('dry_run', False))
        fill_metadata = bool(payload.get('fill_metadata', True))
        try:
            limit = int(payload.get('limit', 5000))
        except (TypeError, ValueError):
            return {'error': 'limit must be int'}, 400
        try:
            body = ensure_allowlist_species_materialized(
                app_config.get,
                fill_metadata=fill_metadata,
                dry_run=dry_run,
                limit=limit,
            )
            bust_response_caches()
            bust_system_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Materialize allowlist failed: %s', e)
            return {'error': str(e)}, 500

    @app.route(
        '/api/ui/system/species-registry/repair-cards/start',
        methods=['POST'],
    )
    def species_registry_repair_cards_start():
        """Start background repair for species cards."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with uis._catalog_cards_lock:
            if uis._catalog_cards_status.get('status') == 'running':
                return {
                    'error': 'Repair already running',
                    'status': uis._catalog_cards_status,
                }, 409
            payload = request.get_json(silent=True) or {}
            try:
                limit = int(payload.get('limit', 6000))
            except (TypeError, ValueError):
                return {'error': 'limit must be int'}, 400
            cov_before = catalog_cards_coverage_snapshot(app_config.get)
            uis._catalog_cards_status.update({
                'status': 'running',
                'result': None,
                'error': None,
                'progress': {
                    'limit': limit,
                    'coverage_before': cov_before,
                },
            })

            def _run():
                try:
                    with app.app_context():
                        result = repair_catalog_cards(
                            app_config.get,
                            dry_run=False,
                            limit=limit,
                        )
                        cov_after = catalog_cards_coverage_snapshot(
                            app_config.get,
                        )
                    with uis._catalog_cards_lock:
                        merged = {**result, 'coverage_after': cov_after}
                        uis._catalog_cards_status.update({
                            'status': 'done',
                            'result': merged,
                            'error': None,
                        })
                except Exception as e:
                    with uis._catalog_cards_lock:
                        uis._catalog_cards_status.update({
                            'status': 'error',
                            'result': None,
                            'error': str(e),
                        })

            threading.Thread(target=_run, daemon=True).start()
            return {
                'message': 'Catalog cards repair started',
                'status': uis._catalog_cards_status,
            }, 202

    @app.route(
        '/api/ui/system/species-registry/repair-cards/status',
        methods=['GET'],
    )
    def species_registry_repair_cards_status():
        """Read background repair status with live coverage counters."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        with uis._catalog_cards_lock:
            snap = dict(uis._catalog_cards_status)
        snap['coverage_now'] = catalog_cards_coverage_snapshot(app_config.get)
        snap['schedule'] = uis._catalog_cards_schedule_state()
        return snap, 200

    @app.route('/api/ui/system/species-registry/data-quality', methods=['GET'])
    def species_registry_data_quality():
        """Отчёт: мусор в каталоге, дубликаты имён (слияние)."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.species_data_quality_service import (
            build_data_quality_report,
        )

        dup_limit = request.args.get('duplicate_limit', type=int) or 80
        dup_limit = max(10, min(dup_limit, 500))
        try:
            body = build_data_quality_report(
                db.session,
                duplicate_group_limit=dup_limit,
            )
            return body, 200
        except Exception as e:
            app.logger.exception('Species data quality report failed: %s', e)
            return {'error': str(e)}, 500

    @app.route(
        '/api/ui/system/species-registry/classifier-dataset-alignment',
        methods=['GET'],
    )
    def species_registry_classifier_dataset_alignment():
        """Classifier classes vs Species catalog vs dataset folders."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.species_dataset_alignment_service import (
            build_classifier_dataset_alignment_report,
        )

        clf_lim = request.args.get('classifier_limit', type=int) or 600
        cat_lim = request.args.get('catalog_limit', type=int) or 400
        ds_lim = request.args.get('dataset_limit', type=int) or 200
        try:
            body = build_classifier_dataset_alignment_report(
                db.session,
                app_config.get,
                classifier_limit=clf_lim,
                catalog_limit=cat_lim,
                dataset_limit=ds_lim,
            )
            return body, 200
        except Exception as e:
            app.logger.exception(
                'Classifier/dataset alignment report failed: %s', e,
            )
            return {'error': str(e)}, 500

    @app.route(
        '/api/ui/system/species-registry/coverage-metrics',
        methods=['GET'],
    )
    def species_registry_coverage_metrics():
        """Coverage: observed / dataset / full EU catalog segments."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        from services.species_dataset_alignment_service import (
            build_catalog_coverage_metrics,
        )

        try:
            body = build_catalog_coverage_metrics(db.session, app_config.get)
            return body, 200
        except Exception as e:
            app.logger.exception('Catalog coverage metrics failed: %s', e)
            return {'error': str(e)}, 500

    @app.route(
        '/api/ui/system/species-registry/tuning-targets/export',
        methods=['GET'],
    )
    def species_registry_tuning_targets_export():
        """Export manually marked tuning targets for training pipeline."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        raw = app_config.get('species.tuning_target_species_ids') or []
        ids = []
        if isinstance(raw, list):
            for x in raw:
                try:
                    v = int(x)
                except (TypeError, ValueError):
                    continue
                if v > 0:
                    ids.append(v)
        ids = sorted(set(ids))
        rows = Species.query.filter(Species.id.in_(ids)).all() if ids else []
        by_id = {s.id: s for s in rows}

        fmt = (request.args.get('format') or 'json').strip().lower()
        body_rows = [
            {'id': sid, 'name': by_id[sid].name}
            for sid in ids
            if sid in by_id
        ]
        if fmt == 'csv':
            buf = io.StringIO()
            wr = csv.writer(buf)
            wr.writerow(['species_id', 'species_name'])
            for r in body_rows:
                wr.writerow([r['id'], r['name']])
            disp = 'attachment; filename="birdlense_tuning_targets.csv"'
            return Response(
                buf.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': disp},
            )
        return {'count': len(body_rows), 'targets': body_rows}, 200
