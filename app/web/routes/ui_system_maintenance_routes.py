"""Scan recordings, visits maintenance, species merge/reconcile (#265)."""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone

from flask import request

import routes.ui_system_jobs_state as job_state
from app_config.app_config import app_config
from auth import admin_track_regen_access
from models import ActivityLog, Species, SpeciesVisit, Video, VideoSpecies, db
from services.http_response_cache import (
    bust_response_caches,
    bust_system_response_caches,
)
from services.legacy_import_cleanup_service import (
    cleanup_legacy_import_placeholders as _cleanup_legacy_import_placeholders,
)
from services.species_merge_service import merge_species_into
from services.species_registry_service import resolve_species_name
from services.species_visit_maintenance_service import (
    apply_clean_orphaned_visits,
    apply_realign_visit_times,
    apply_split_large_gap_visits,
    preview_clean_orphaned_visits,
    preview_realign_visit_times,
    preview_split_large_gap_visits,
)
from sqlalchemy import exists, func, select
from util import settings_check_access, recordings_dir
import util as util_mod


def register_ui_system_maintenance_routes(app):
    """Импорт с диска и обслуживание видов/визитов."""

    @app.route('/api/ui/system/recordings/scan', methods=['POST'])
    def scan_recordings():
        """
        Scan data/recordings/ for video.mp4 not in DB and add them.
        Fixes recordings missing from stats after server restart.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        if not os.path.exists(recordings_dir()):
            return {'imported': 0, 'message': 'No recordings directory'}, 200

        existing_paths = {
            v.video_path for v in db.session.query(Video.video_path).all()
        }
        imported = 0
        cleaned_legacy_placeholders = 0
        cleaned_legacy_visits = 0
        # YYYY/MM/DD/HHMMSS или YYYY/MM/DD/HH-MM-SS
        pattern = re.compile(
            r'^(\d{4})/(\d{2})/(\d{2})/(\d{2})[-:]?(\d{2})[-:]?(\d{2})$'
        )

        try:
            cleaned_legacy_placeholders, cleaned_legacy_visits = (
                _cleanup_legacy_import_placeholders()
            )
            rec_dir = recordings_dir()
            for year in os.listdir(rec_dir):
                year_path = os.path.join(rec_dir, year)
                if not os.path.isdir(year_path) or not year.isdigit():
                    continue
                for month in os.listdir(year_path):
                    month_path = os.path.join(year_path, month)
                    if not os.path.isdir(month_path) or not month.isdigit():
                        continue
                    for day in os.listdir(month_path):
                        day_path = os.path.join(month_path, day)
                        if not os.path.isdir(day_path) or not day.isdigit():
                            continue
                        for ts in os.listdir(day_path):
                            ts_path = os.path.join(day_path, ts)
                            if not os.path.isdir(ts_path):
                                continue
                            m = pattern.match(f'{year}/{month}/{day}/{ts}')
                            if not m:
                                continue
                            video_mp4 = os.path.join(ts_path, 'video.mp4')
                            if not os.path.isfile(video_mp4):
                                continue
                            try:
                                if os.path.getsize(video_mp4) <= 0:
                                    continue
                            except OSError:
                                continue
                            rel_path = f'data/recordings/{year}/{month}/{day}/{ts}/video.mp4'
                            if rel_path in existing_paths:
                                continue

                            try:
                                with db.session.begin_nested():
                                    y, mo, d, h, mi, s = map(int, m.groups())
                                    start_time = datetime(
                                        y, mo, d, h, mi, s,
                                        tzinfo=timezone.utc
                                    )
                                    end_time = start_time + timedelta(
                                        seconds=30
                                    )
                                    spectrogram = None
                                    for f in os.listdir(ts_path):
                                        if (f.startswith('spectrogram') and
                                                f.endswith('.jpg')):
                                            spectrogram = f'data/recordings/{year}/{month}/{day}/{ts}/{f}'
                                            break

                                    video = Video(
                                        processor_version='1',
                                        start_time=start_time,
                                        end_time=end_time,
                                        video_path=rel_path,
                                        spectrogram_path=spectrogram,
                                    )
                                    db.session.add(video)
                                existing_paths.add(rel_path)
                                imported += 1
                            except Exception as e:
                                app.logger.warning(
                                    f'Import failed {rel_path}: {e}'
                                )
                                continue

            db.session.commit()
            bust_response_caches()
            bust_system_response_caches()

            # Auto-start spectrogram regeneration for newly imported videos (если не запущена)
            spectrogram_started = False
            if imported > 0:
                run_sg = app.extensions.get('birdlense', {}).get(
                    'run_regenerate_spectrograms',
                )
                if run_sg is not None:
                    with job_state._regenerate_lock:
                        if job_state._regenerate_status['status'] != 'running':
                            t = threading.Thread(
                                target=run_sg,
                                args=(False, None, None, None),
                                daemon=True,
                            )
                            t.start()
                            spectrogram_started = True

            message = f'Imported {imported} recordings'
            if cleaned_legacy_placeholders:
                message += (
                    f'; cleaned {cleaned_legacy_placeholders} legacy placeholders'
                )
            return {
                'imported': imported,
                'cleaned_legacy_placeholders': cleaned_legacy_placeholders,
                'cleaned_legacy_visits': cleaned_legacy_visits,
                'message': message,
                'spectrogramRegenerationStarted': spectrogram_started,
            }, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Scan recordings failed')
            return {'error': 'Failed to scan recordings'}, 500

    @app.route('/api/ui/system/clean-orphaned-visits', methods=['POST'])
    def clean_orphaned_visits():
        """
        Удалить осиротевшие SpeciesVisit (без VideoSpecies) и синхронизировать
        VideoSpecies.species_id с visit.species_id. Исправляет некорректные счётчики
        в календаре миграций и каталоге после старых коррекций.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            if dry_run:
                return preview_clean_orphaned_visits(db.session), 200

            body = apply_clean_orphaned_visits(db.session)
            db.session.commit()
            bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Clean orphaned visits failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/realign-visit-times', methods=['POST'])
    def realign_visit_times():
        """Preview/apply SpeciesVisit time realignment from actual detection timestamps."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            if dry_run:
                return preview_realign_visit_times(db.session), 200

            body = apply_realign_visit_times(db.session)
            db.session.commit()
            bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Realign visit times failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/split-large-gap-visits', methods=['POST'])
    def split_large_gap_visits():
        """Preview/apply splitting of visits with large internal detection gaps."""
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            gap_seconds = int(app_config.get('detection.dedup_window_seconds') or 60)
            if dry_run:
                return preview_split_large_gap_visits(db.session, gap_seconds), 200

            body = apply_split_large_gap_visits(db.session, gap_seconds)
            db.session.commit()
            bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Split large-gap visits failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/merge-duplicate-species', methods=['POST'])
    def merge_duplicate_species():
        """
        Объединить дубликаты видов (Garrulus glandarius (Eurasian Jay) -> Eurasian Jay).
        Использует species_canonical_mapping.txt. Сопоставление без учёта регистра.
        """
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            from util import load_species_canonical_mapping
            mapping = load_species_canonical_mapping()
            if not mapping:
                return {'merged': 0, 'message': 'No species_canonical_mapping.txt'}, 200
            # variant_lower -> canonical (для сопоставления без учёта регистра)
            variant_to_canonical = {}
            for variant, canonical in mapping.items():
                variant_to_canonical[variant] = canonical
                variant_to_canonical[variant.lower().strip()] = canonical
            canonical_to_species = {}  # canonical -> [Species]
            for sp in Species.query.all():
                canonical = variant_to_canonical.get(sp.name) or variant_to_canonical.get(sp.name.lower().strip())
                if canonical:
                    canonical_to_species.setdefault(canonical, []).append(sp)
            merged = 0
            details = []
            for canonical, species_list in canonical_to_species.items():
                if len(species_list) <= 1:
                    continue
                target = next((s for s in species_list if s.name == canonical), species_list[0])
                for other in [s for s in species_list if s.id != target.id]:
                    if target.name != canonical:
                        target.name = canonical
                    merge_species_into(other.id, target.id)
                    details.append(f"{other.name} -> {canonical}")
                    merged += 1
            db.session.commit()
            bust_response_caches()
            return {'merged': merged, 'details': details, 'message': f'Merged {merged} duplicate species'}, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Merge duplicate species failed: %s', e)
            return {'error': str(e)}, 500

    @app.route('/api/ui/system/species-catalog/reconcile', methods=['POST'])
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
        if not settings_check_access():
            return {'error': 'Password required'}, 403
        try:
            from services.species_catalog_allowlist_service import clear_allowlist_cache
            from services.species_catalog_reconcile_service import reconcile_species_catalog

            payload = request.get_json(silent=True) or {}
            dry_run = bool(payload.get('dry_run', True))
            dup_limit = payload.get('duplicate_group_limit', 500)
            try:
                dup_limit = int(dup_limit)
            except (TypeError, ValueError):
                return {'error': 'duplicate_group_limit must be int'}, 400
            dup_limit = max(10, min(dup_limit, 5000))

            body = reconcile_species_catalog(
                dry_run=dry_run,
                merge_normalized_duplicate_names=bool(
                    payload.get('merge_normalized_duplicate_names', True),
                ),
                reassign_suspects_to_unknown=bool(
                    payload.get('reassign_suspects_to_unknown', False),
                ),
                reassign_off_allowlist_to_unknown=bool(
                    payload.get('reassign_off_allowlist_to_unknown', False),
                ),
                delete_empty_suspects=bool(payload.get('delete_empty_suspects', False)),
                delete_empty_off_allowlist=bool(
                    payload.get('delete_empty_off_allowlist', False),
                ),
                duplicate_group_limit=dup_limit,
                app_config_get=app_config.get,
            )
            if not dry_run:
                clear_allowlist_cache()
                bust_response_caches()
            return body, 200
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Species catalog reconcile failed: %s', e)
            return {'error': str(e)}, 500
