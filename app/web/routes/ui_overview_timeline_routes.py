"""Overview, region, migration calendar, timeline, export, PDF report, unknowns (#198)."""

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone

from flask import Response, request
from sqlalchemy import or_

from app_config.app_config import app_config
from models import Species, SpeciesVisit, Video, VideoSpecies, db
from species_constants import GENERIC_BIRD_SPECIES
from services.cache import cache_get, cache_set
from services.ebird_export_service import build_ebird_csv
from services.ebird_region_service import get_region_comparison
from services.migration_calendar_service import get_migration_calendar
from services.overview_service import get_overview_data
from services.report_service import build_monthly_report, get_monthly_report_data
from util import ensure_utc, observer_local_day_bounds, observer_local_range, parse_utc_timestamp

from routes.ui_route_constants import (
    CACHE_MIGRATION_SEC,
    CACHE_TIMELINE_SEC,
    CACHE_UNKNOWNS_SEC,
    UNKNOWNS_LIMIT_MAX,
)
from routes.ui_timeline_helpers import build_merged_timeline_items, parse_timeline_iso


def fetch_review_queue_items(
    session,
    *,
    date_param: str | None = None,
    time_of_day: str = 'all',
    hour: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Low-confidence review queue with explicit review-state fields."""
    limit = min(max(int(limit or 100), 1), UNKNOWNS_LIMIT_MAX)
    if date_param:
        try:
            start_dt, end_dt = observer_local_range(
                date_param,
                time_of_day=time_of_day,
                hour=hour,
            )
        except ValueError as exc:
            raise ValueError('Invalid local date range parameters') from exc
    else:
        if not start_time or not end_time:
            raise ValueError('Both start_time and end_time are required')
        try:
            start_dt = parse_utc_timestamp(start_time)
            end_dt = parse_utc_timestamp(end_time)
        except ValueError as exc:
            raise ValueError('Invalid datetime format') from exc

    if end_dt - start_dt > timedelta(days=1):
        raise ValueError('Interval must not exceed 1 day')

    threshold = float(app_config.get('ui.unknown_confidence_threshold') or 0.5)
    threshold = max(0.0, min(1.0, threshold))

    rows = (
        session.query(VideoSpecies)
        .join(Video)
        .join(Species)
        .filter(
            Video.end_time >= start_dt,
            Video.start_time <= end_dt,
            VideoSpecies.manually_corrected == False,
            or_(
                VideoSpecies.confidence < threshold,
                Species.name == GENERIC_BIRD_SPECIES,
            ),
        )
        .order_by(VideoSpecies.created_at.desc())
        .limit(limit * 3)
        .all()
    )

    result = []
    for vs in rows:
        frames = (vs.frames or '').strip() if getattr(vs, 'frames', None) else ''
        if (
            vs.detection_provider == 'legacy'
            and vs.species.name == 'Unknown'
            and float(vs.confidence or 0) <= 0
            and vs.source == 'video'
            and not vs.manually_corrected
            and vs.track_id is None
            and not frames
            and float(vs.start_time or 0) == 0
            and float(vs.end_time or 0) == 30
        ):
            continue
        video_start = ensure_utc(vs.video.start_time)
        det_time = video_start + timedelta(seconds=vs.start_time)
        review_reason = 'generic_bird' if vs.species.name == GENERIC_BIRD_SPECIES else 'low_confidence'
        result.append({
            'id': vs.id,
            'video_id': vs.video_id,
            'species_id': vs.species_id,
            'species_name': vs.species.name,
            'confidence': round(vs.confidence, 4),
            'start_time': det_time.astimezone(timezone.utc).isoformat(),
            'end_time': (video_start + timedelta(seconds=vs.end_time)).astimezone(timezone.utc).isoformat(),
            'source': vs.source,
            'detection_provider': vs.detection_provider,
            'image_url': vs.species.image_url,
            'review_state': 'pending',
            'review_reason': review_reason,
            'review_source': 'unknowns',
        })
        if len(result) >= limit:
            break

    return result


def register_ui_overview_timeline_routes(app):
    @app.route('/api/ui/overview', methods=['GET'])
    def get_overview():
        date_param = request.args.get('date', None)
        start_time_param = request.args.get('start_time', None)
        end_time_param = request.args.get('end_time', None)
        try:
            if date_param:
                start_of_day, end_of_day = observer_local_day_bounds(date_param)
            elif start_time_param and end_time_param:
                start_of_day = parse_utc_timestamp(start_time_param)
                end_of_day = parse_utc_timestamp(end_time_param)
            else:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        except (ValueError, TypeError):
            return {"error": "Invalid timestamp format."}, 400

        data = get_overview_data(db.session, start_of_day, end_of_day)
        return data, 200

    @app.route('/api/ui/region-comparison', methods=['GET'])
    def get_region_comparison_route():
        """Compare user's observed species with eBird region top. Requires secrets.ebird_api_key."""
        observed = (
            db.session.query(Species.name)
            .join(SpeciesVisit, SpeciesVisit.species_id == Species.id)
            .filter(Species.name != GENERIC_BIRD_SPECIES)
            .distinct()
            .all()
        )
        user_names = [r[0] for r in observed]
        result = get_region_comparison(user_names)
        return result if result is not None else {}, 200

    @app.route('/api/ui/migration-calendar', methods=['GET'])
    def get_migration_calendar_route():
        """Species activity by month — historical pattern for migration calendar."""
        start_year = request.args.get('start_year', type=int)
        end_year = request.args.get('end_year', type=int)
        start_date = request.args.get('start_date', type=str)
        end_date = request.args.get('end_date', type=str)
        catalog = (request.args.get('catalog') or 'observed').strip().lower()
        evidence = 'all'
        if catalog not in ('observed', 'dataset', 'full_eu', 'active', 'full'):
            return {'error': 'catalog must be observed, dataset or full_eu'}, 400
        if start_date and not re.match(r'^\d{4}-\d{2}-\d{2}$', start_date):
            return {'error': 'start_date must be YYYY-MM-DD'}, 400
        if end_date and not re.match(r'^\d{4}-\d{2}-\d{2}$', end_date):
            return {'error': 'end_date must be YYYY-MM-DD'}, 400
        if start_date and end_date and start_date > end_date:
            return {'error': 'start_date must be <= end_date'}, 400
        mck = (
            f"migration_cal:v3:{start_year}:{end_year}:{start_date}:{end_date}:"
            f"{catalog}:{evidence}"
        )
        hit, mcached = cache_get(mck)
        if hit:
            return mcached, 200
        data = get_migration_calendar(
            db.session,
            start_year=start_year,
            end_year=end_year,
            start_date=start_date,
            end_date=end_date,
            catalog=catalog,
            evidence=evidence,
            app_config_get=app_config.get,
        )
        cache_set(mck, data, CACHE_MIGRATION_SEC)
        return data, 200

    @app.route('/api/ui/timeline', methods=['GET'])
    def get_video_species():
        date_param = request.args.get('date')
        time_of_day = (request.args.get('time_of_day') or 'all').strip().lower()
        hour_param = request.args.get('hour', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')

        if date_param:
            try:
                start_dt, end_dt = observer_local_range(
                    date_param,
                    time_of_day=time_of_day,
                    hour=hour_param,
                )
            except ValueError:
                return {'error': 'Invalid local date range parameters'}, 400
            tck = f"timeline:local:{date_param}:{time_of_day}:{hour_param}"
        else:
            if not start_time or not end_time:
                return {'error': 'Both start_time and end_time are required'}, 400
            try:
                start_dt = parse_utc_timestamp(start_time)
                end_dt = parse_utc_timestamp(end_time)
            except ValueError:
                return {'error': 'Invalid datetime format'}, 400
            tck = f"timeline:{start_time}:{end_time}"
        hit, tcached = cache_get(tck)
        if hit:
            return tcached

        if end_dt - start_dt > timedelta(days=1):
            return {'error': 'The interval between start_time and end_time must not exceed 1 day'}, 400

        response = build_merged_timeline_items(db.session, start_dt, end_dt)
        cache_set(tck, response, CACHE_TIMELINE_SEC)
        return response

    @app.route('/api/ui/timeline/export', methods=['GET'])
    def export_timeline():
        """Export timeline data as CSV or JSON. Same params as /api/ui/timeline."""
        date_param = request.args.get('date')
        time_of_day = (request.args.get('time_of_day') or 'all').strip().lower()
        hour_param = request.args.get('hour', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        fmt = request.args.get('format', 'json').lower()

        if fmt not in ('csv', 'json', 'ebird'):
            return {'error': 'format must be csv, json, or ebird'}, 400

        if date_param:
            try:
                start_dt, end_dt = observer_local_range(
                    date_param,
                    time_of_day=time_of_day,
                    hour=hour_param,
                )
            except ValueError:
                return {'error': 'Invalid local date range parameters'}, 400
        else:
            if not start_time or not end_time:
                return {'error': 'Both start_time and end_time are required'}, 400
            try:
                start_dt = parse_utc_timestamp(start_time)
                end_dt = parse_utc_timestamp(end_time)
            except ValueError:
                return {'error': 'Invalid datetime format'}, 400

        if end_dt - start_dt > timedelta(days=1):
            return {'error': 'Interval must not exceed 1 day'}, 400

        merged = build_merged_timeline_items(db.session, start_dt, end_dt)

        rows = []
        for item in merged:
            st_p = parse_timeline_iso(item['start_time'])
            et_p = parse_timeline_iso(item['end_time'])
            duration = max(0, round((et_p - st_p).total_seconds()))
            w = item.get('weather') or {}
            rows.append({
                'id': item['id'],
                'species_name': item['species']['name'],
                'start_time': st_p.astimezone(timezone.utc).isoformat(),
                'end_time': et_p.astimezone(timezone.utc).isoformat(),
                'duration_sec': duration,
                'max_simultaneous': item.get('max_simultaneous', 1),
                'detection_count': len(item.get('detections') or []),
                'temp': w.get('temp'),
                'clouds': w.get('clouds'),
            })

        if fmt == 'ebird':
            seen = set()
            ebird_rows = []
            for r in rows:
                name = r.get('species_name', '')
                if name and name not in seen:
                    seen.add(name)
                    ebird_rows.append(r)
            body = build_ebird_csv(ebird_rows, start_dt, end_dt)
            return Response(
                body,
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=birdlense_ebird.csv'},
            )

        if fmt == 'json':
            body = json.dumps(rows, ensure_ascii=False, indent=2)
            return Response(
                body,
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=birdlense_timeline.json'},
            )

        if not rows:
            output = io.StringIO()
            w = csv.writer(output)
            w.writerow([
                'id', 'species_name', 'start_time', 'end_time', 'duration_sec',
                'max_simultaneous', 'detection_count', 'temp', 'clouds',
            ])
        else:
            output = io.StringIO()
            w = csv.writer(output)
            w.writerow(rows[0].keys())
            for r in rows:
                w.writerow(r.values())
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=birdlense_timeline.csv'},
        )

    @app.route('/api/ui/report/pdf', methods=['GET'])
    def report_pdf():
        """Monthly PDF report: N species, top 5, stats, chart."""
        month_param = request.args.get('month')
        start_param = request.args.get('start_time')
        end_param = request.args.get('end_time')

        if month_param:
            try:
                year, month = map(int, month_param.split('-'))
                start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
                if month == 12:
                    end_dt = (
                        datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
                        - timedelta(seconds=1)
                    )
                else:
                    end_dt = (
                        datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
                        - timedelta(seconds=1)
                    )
                month_label = start_dt.strftime('%B %Y')
            except (ValueError, IndexError):
                return {'error': 'Invalid month format. Use YYYY-MM'}, 400
        elif start_param and end_param:
            try:
                start_dt = parse_utc_timestamp(start_param)
                end_dt = parse_utc_timestamp(end_param)
                if end_dt - start_dt > timedelta(days=93):
                    return {'error': 'Interval must not exceed 3 months'}, 400
                month_label = f"{start_dt.strftime('%Y-%m-%d')} — {end_dt.strftime('%Y-%m-%d')}"
            except ValueError:
                return {'error': 'Invalid datetime format'}, 400
        else:
            return {'error': 'Provide month=YYYY-MM or start_time and end_time'}, 400

        top_species, stats = get_monthly_report_data(db.session, start_dt, end_dt)
        pdf_bytes = build_monthly_report(start_dt, end_dt, top_species, stats, month_label)

        filename = f"birdlense_report_{start_dt.strftime('%Y%m')}.pdf"
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'},
        )

    @app.route('/api/ui/unknowns', methods=['GET'])
    def get_unknowns():
        """List of low-confidence detections for manual review."""
        date_param = request.args.get('date')
        time_of_day = (request.args.get('time_of_day') or 'all').strip().lower()
        hour_param = request.args.get('hour', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        limit = request.args.get('limit', 100, type=int)

        uck = (
            f"unknowns:{date_param or start_time}:{time_of_day}:{hour_param}:"
            f"{end_time}:{limit}:{app_config.get('ui.unknown_confidence_threshold')}"
        )
        hit, uc = cache_get(uck)
        if hit:
            return uc
        try:
            result = fetch_review_queue_items(
                db.session,
                date_param=date_param,
                time_of_day=time_of_day,
                hour=hour_param,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
        except ValueError as exc:
            return {'error': str(exc)}, 400

        cache_set(uck, result, CACHE_UNKNOWNS_SEC)
        return result
