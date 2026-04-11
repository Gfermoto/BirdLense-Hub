"""Логика system maintenance: scan recordings, visits, species merge/reconcile (#293)."""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import routes.ui_system_jobs_state as job_state
from app_config.app_config import app_config
from models import Species, Video, db
from services.http_response_cache import (
    bust_response_caches,
    bust_system_response_caches,
)
from services.legacy_import_cleanup_service import (
    cleanup_legacy_import_placeholders as _cleanup_legacy_import_placeholders,
)
from services.species_merge_service import merge_species_into
from services.species_visit_maintenance_service import (
    apply_clean_orphaned_visits,
    apply_realign_visit_times,
    apply_split_large_gap_visits,
    preview_clean_orphaned_visits,
    preview_realign_visit_times,
    preview_split_large_gap_visits,
)
from util import recordings_dir

if TYPE_CHECKING:
    from flask import Flask

_log = logging.getLogger(__name__)

_TS_DIR_PATTERN = re.compile(
    r'^(\d{4})/(\d{2})/(\d{2})/(\d{2})[-:]?(\d{2})[-:]?(\d{2})$',
)


def coerce_duplicate_group_limit(raw: object, default: int = 500) -> tuple[int | None, str | None]:
    """Parse duplicate_group_limit for species-catalog reconcile; (value, None) or (None, err)."""
    if raw is None:
        raw = default
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None, 'duplicate_group_limit must be int'
    return max(10, min(v, 5000)), None


def run_recordings_scan(flask_app: Flask) -> tuple[dict, int]:
    """
    Scan data/recordings/ for video.mp4 not in DB and add them.
    On success may start spectrogram regen thread via app.extensions (if registered).
    """
    if not os.path.exists(recordings_dir()):
        return {'imported': 0, 'message': 'No recordings directory'}, 200

    existing_paths = {
        v.video_path for v in db.session.query(Video.video_path).all()
    }
    imported = 0
    cleaned_legacy_placeholders = 0
    cleaned_legacy_visits = 0

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
                        m = _TS_DIR_PATTERN.match(f'{year}/{month}/{day}/{ts}')
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
                                    tzinfo=timezone.utc,
                                )
                                end_time = start_time + timedelta(seconds=30)
                                spectrogram = None
                                for f in os.listdir(ts_path):
                                    if f.startswith('spectrogram') and f.endswith('.jpg'):
                                        spectrogram = (
                                            f'data/recordings/{year}/{month}/{day}/{ts}/{f}'
                                        )
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
                            _log.warning('Import failed %s: %s', rel_path, e)
                            continue

        db.session.commit()
        bust_response_caches()
        bust_system_response_caches()

        spectrogram_started = False
        if imported > 0:
            run_sg = flask_app.extensions.get('birdlense', {}).get(
                'run_regenerate_spectrograms',
            )
            if run_sg is not None:
                with job_state._regenerate_lock:
                    if job_state._regenerate_status['status'] != 'running':
                        threading.Thread(
                            target=run_sg,
                            args=(False, None, None, None),
                            daemon=True,
                        ).start()
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
    except Exception:
        db.session.rollback()
        _log.exception('Scan recordings failed')
        return {'error': 'Failed to scan recordings'}, 500


def post_clean_orphaned_visits(payload: dict) -> tuple[dict, int]:
    try:
        dry_run = bool(payload.get('dry_run', True))
        if dry_run:
            return preview_clean_orphaned_visits(db.session), 200

        body = apply_clean_orphaned_visits(db.session)
        db.session.commit()
        bust_response_caches()
        return body, 200
    except Exception as e:
        db.session.rollback()
        _log.exception('Clean orphaned visits failed: %s', e)
        return {'error': str(e)}, 500


def post_realign_visit_times(payload: dict) -> tuple[dict, int]:
    try:
        dry_run = bool(payload.get('dry_run', True))
        if dry_run:
            return preview_realign_visit_times(db.session), 200

        body = apply_realign_visit_times(db.session)
        db.session.commit()
        bust_response_caches()
        return body, 200
    except Exception as e:
        db.session.rollback()
        _log.exception('Realign visit times failed: %s', e)
        return {'error': str(e)}, 500


def post_split_large_gap_visits(payload: dict) -> tuple[dict, int]:
    try:
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
        _log.exception('Split large-gap visits failed: %s', e)
        return {'error': str(e)}, 500


def post_merge_duplicate_species() -> tuple[dict, int]:
    try:
        from util import load_species_canonical_mapping

        mapping = load_species_canonical_mapping()
        if not mapping:
            return {'merged': 0, 'message': 'No species_canonical_mapping.txt'}, 200
        variant_to_canonical: dict[str, str] = {}
        for variant, canonical in mapping.items():
            variant_to_canonical[variant] = canonical
            variant_to_canonical[variant.lower().strip()] = canonical
        canonical_to_species: dict[str, list[Species]] = {}
        for sp in Species.query.all():
            canonical = variant_to_canonical.get(sp.name) or variant_to_canonical.get(
                sp.name.lower().strip(),
            )
            if canonical:
                canonical_to_species.setdefault(canonical, []).append(sp)
        merged = 0
        details: list[str] = []
        for canonical, species_list in canonical_to_species.items():
            if len(species_list) <= 1:
                continue
            target = next((s for s in species_list if s.name == canonical), species_list[0])
            for other in [s for s in species_list if s.id != target.id]:
                if target.name != canonical:
                    target.name = canonical
                merge_species_into(other.id, target.id)
                details.append(f'{other.name} -> {canonical}')
                merged += 1
        db.session.commit()
        bust_response_caches()
        return {
            'merged': merged,
            'details': details,
            'message': f'Merged {merged} duplicate species',
        }, 200
    except Exception as e:
        db.session.rollback()
        _log.exception('Merge duplicate species failed: %s', e)
        return {'error': str(e)}, 500


def post_species_catalog_reconcile(payload: dict) -> tuple[dict, int]:
    from services.species_catalog_allowlist_service import clear_allowlist_cache
    from services.species_catalog_reconcile_service import reconcile_species_catalog

    try:
        dry_run = bool(payload.get('dry_run', True))
        dup_limit, err = coerce_duplicate_group_limit(
            payload.get('duplicate_group_limit', 500),
        )
        if err:
            return {'error': err}, 400

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
        _log.exception('Species catalog reconcile failed: %s', e)
        return {'error': str(e)}, 500
