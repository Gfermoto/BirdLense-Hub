"""Overview, region, migration calendar, timeline, export, PDF report, unknowns (#198)."""

from datetime import timedelta

from flask import Response, request
from app_config.app_config import app_config
from auth import ui_sensitive_export_access
from models import db
from services.cache import cache_get, cache_set
from services.ebird_region_service import (
    get_region_comparison,
    list_observed_species_names_for_comparison,
)
from services.migration_calendar_request_service import (
    migration_calendar_cache_key,
    validate_migration_calendar_params,
)
from services.migration_calendar_service import get_migration_calendar
from services.monthly_report_window_service import (
    MonthlyReportWindowError,
    resolve_monthly_report_window,
)
from services.overview_request_service import OverviewWindowError, resolve_overview_window
from services.overview_service import get_overview_data
from services.report_service import build_monthly_report, get_monthly_report_data
from services.review_queue_service import fetch_review_queue_items
from services.timeline_export_service import (
    build_timeline_export_response_parts,
    build_timeline_export_rows,
    validate_timeline_export_format,
)
from services.timeline_window_service import TimelineWindowError, resolve_timeline_utc_window
from routes.ui_route_constants import (
    CACHE_MIGRATION_SEC,
    CACHE_TIMELINE_SEC,
    CACHE_UNKNOWNS_SEC,
)
from routes.ui_timeline_helpers import build_merged_timeline_items


def _favorite_only_from_request() -> bool:
    raw = (request.args.get("favorite_only") or request.args.get("favorites") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def register_ui_overview_timeline_routes(app):
    @app.route("/api/ui/overview", methods=["GET"])
    def get_overview():
        date_param = request.args.get("date", None)
        start_time_param = request.args.get("start_time", None)
        end_time_param = request.args.get("end_time", None)
        try:
            start_of_day, end_of_day = resolve_overview_window(
                date_param,
                start_time_param,
                end_time_param,
            )
        except OverviewWindowError as exc:
            return {"error": str(exc)}, 400

        data = get_overview_data(db.session, start_of_day, end_of_day)
        return data, 200

    @app.route("/api/ui/region-comparison", methods=["GET"])
    def get_region_comparison_route():
        """Compare user's observed species with eBird region top. Requires secrets.ebird_api_key."""
        user_names = list_observed_species_names_for_comparison(db.session)
        result = get_region_comparison(user_names)
        return result if result is not None else {}, 200

    @app.route("/api/ui/migration-calendar", methods=["GET"])
    def get_migration_calendar_route():
        """Species activity by month — historical pattern for migration calendar."""
        start_year = request.args.get("start_year", type=int)
        end_year = request.args.get("end_year", type=int)
        start_date = request.args.get("start_date", type=str)
        end_date = request.args.get("end_date", type=str)
        catalog = (request.args.get("catalog") or "observed").strip().lower()
        metric = (request.args.get('metric') or 'encounters').strip().lower()
        evidence = "all"
        param_err = validate_migration_calendar_params(
            catalog,
            start_date,
            end_date,
            metric=metric,
        )
        if param_err:
            return {"error": param_err}, 400
        mck = migration_calendar_cache_key(
            start_year,
            end_year,
            start_date,
            end_date,
            catalog,
            evidence,
            metric=metric,
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
            metric=metric,
            app_config_get=app_config.get,
        )
        cache_set(mck, data, CACHE_MIGRATION_SEC)
        return data, 200

    @app.route("/api/ui/migration-calendar/compare", methods=["GET"])
    def get_migration_calendar_compare_route():
        """Compare encounters (visits) vs max_simultaneous totals per species."""
        start_year = request.args.get("start_year", type=int)
        end_year = request.args.get("end_year", type=int)
        start_date = request.args.get("start_date", type=str)
        end_date = request.args.get("end_date", type=str)
        catalog = (request.args.get("catalog") or "observed").strip().lower()
        evidence = "all"
        param_err = validate_migration_calendar_params(
            catalog,
            start_date,
            end_date,
            metric='encounters',
        )
        if param_err:
            return {"error": param_err}, 400

        compare_cache_key = (
            "migration_cal_compare:v1:"
            f"{start_year}:{end_year}:{start_date}:{end_date}:{catalog}:{evidence}"
        )
        hit, cached = cache_get(compare_cache_key)
        if hit:
            return cached, 200

        encounters = get_migration_calendar(
            db.session,
            start_year=start_year,
            end_year=end_year,
            start_date=start_date,
            end_date=end_date,
            catalog=catalog,
            evidence=evidence,
            metric='encounters',
            app_config_get=app_config.get,
        )
        max_sim = get_migration_calendar(
            db.session,
            start_year=start_year,
            end_year=end_year,
            start_date=start_date,
            end_date=end_date,
            catalog=catalog,
            evidence=evidence,
            metric='max_simultaneous',
            app_config_get=app_config.get,
        )
        by_name = {}
        for row in encounters.get('species', []):
            name = str(row.get('name') or '').strip()
            if not name:
                continue
            by_name[name] = {
                'id': row.get('id'),
                'name': name,
                'image_url': row.get('image_url'),
                'encounters_total': int(row.get('total') or 0),
                'max_simultaneous_total': 0,
            }
        for row in max_sim.get('species', []):
            name = str(row.get('name') or '').strip()
            if not name:
                continue
            current = by_name.setdefault(
                name,
                {
                    'id': row.get('id'),
                    'name': name,
                    'image_url': row.get('image_url'),
                    'encounters_total': 0,
                    'max_simultaneous_total': 0,
                },
            )
            current['max_simultaneous_total'] = int(row.get('total') or 0)
            if current.get('id') is None:
                current['id'] = row.get('id')
            if not current.get('image_url'):
                current['image_url'] = row.get('image_url')

        species_rows = []
        for item in by_name.values():
            item['delta'] = item['max_simultaneous_total'] - item['encounters_total']
            species_rows.append(item)
        species_rows.sort(
            key=lambda s: (
                -abs(int(s.get('delta') or 0)),
                -(int(s.get('max_simultaneous_total') or 0)),
                (s.get('name') or '').lower(),
            ),
        )
        payload = {
            'catalog': catalog,
            'species': species_rows,
            'totals': {
                'encounters': sum(int(x.get('encounters_total') or 0) for x in species_rows),
                'max_simultaneous': sum(int(x.get('max_simultaneous_total') or 0) for x in species_rows),
            },
        }
        payload['totals']['delta'] = payload['totals']['max_simultaneous'] - payload['totals']['encounters']
        cache_set(compare_cache_key, payload, CACHE_MIGRATION_SEC)
        return payload, 200

    @app.route("/api/ui/timeline", methods=["GET"])
    def get_video_species():
        date_param = request.args.get("date")
        time_of_day = (request.args.get("time_of_day") or "all").strip().lower()
        hour_param = request.args.get("hour", type=int)
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")

        try:
            start_dt, end_dt = resolve_timeline_utc_window(
                date_param=date_param,
                time_of_day=time_of_day,
                hour_param=hour_param,
                start_time=start_time,
                end_time=end_time,
            )
        except TimelineWindowError as exc:
            return {"error": str(exc)}, 400
        fav = 1 if _favorite_only_from_request() else 0
        if date_param:
            tck = f"timeline:local:{date_param}:{time_of_day}:{hour_param}:f{fav}"
        else:
            tck = f"timeline:{start_time}:{end_time}:f{fav}"
        hit, tcached = cache_get(tck)
        if hit:
            return tcached

        if end_dt - start_dt > timedelta(days=1):
            return {"error": "The interval between start_time and end_time must not exceed 1 day"}, 400

        response = build_merged_timeline_items(db.session, start_dt, end_dt, favorite_only=bool(fav))
        cache_set(tck, response, CACHE_TIMELINE_SEC)
        return response

    @app.route("/api/ui/timeline/export", methods=["GET"])
    def export_timeline():
        """Export timeline data as CSV or JSON. Same params as /api/ui/timeline."""
        if not ui_sensitive_export_access():
            return {"error": "Access denied"}, 403
        date_param = request.args.get("date")
        time_of_day = (request.args.get("time_of_day") or "all").strip().lower()
        hour_param = request.args.get("hour", type=int)
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")
        fmt = request.args.get("format", "json").lower()

        fmt_err = validate_timeline_export_format(fmt)
        if fmt_err:
            return {"error": fmt_err}, 400

        try:
            start_dt, end_dt = resolve_timeline_utc_window(
                date_param=date_param,
                time_of_day=time_of_day,
                hour_param=hour_param,
                start_time=start_time,
                end_time=end_time,
            )
        except TimelineWindowError as exc:
            return {"error": str(exc)}, 400

        if end_dt - start_dt > timedelta(days=1):
            return {"error": "Interval must not exceed 1 day"}, 400

        merged = build_merged_timeline_items(
            db.session,
            start_dt,
            end_dt,
            favorite_only=_favorite_only_from_request(),
        )
        rows = build_timeline_export_rows(merged)
        body, mimetype, headers = build_timeline_export_response_parts(
            fmt,
            rows,
            start_dt,
            end_dt,
        )
        return Response(body, mimetype=mimetype, headers=headers)

    @app.route("/api/ui/report/pdf", methods=["GET"])
    def report_pdf():
        """Monthly PDF report: N species, top 5, stats, chart."""
        if not ui_sensitive_export_access():
            return {"error": "Access denied"}, 403
        month_param = request.args.get("month")
        start_param = request.args.get("start_time")
        end_param = request.args.get("end_time")

        try:
            start_dt, end_dt, month_label = resolve_monthly_report_window(
                month_param,
                start_param,
                end_param,
            )
        except MonthlyReportWindowError as exc:
            return {"error": str(exc)}, 400

        top_species, stats = get_monthly_report_data(db.session, start_dt, end_dt)
        pdf_bytes = build_monthly_report(start_dt, end_dt, top_species, stats, month_label)

        filename = f"birdlense_report_{start_dt.strftime('%Y%m')}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/api/ui/unknowns", methods=["GET"])
    def get_unknowns():
        """List of low-confidence detections for manual review."""
        if not ui_sensitive_export_access():
            return {"error": "Access denied"}, 403
        date_param = request.args.get("date")
        time_of_day = (request.args.get("time_of_day") or "all").strip().lower()
        hour_param = request.args.get("hour", type=int)
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")
        limit = request.args.get("limit", 100, type=int)

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
            return {"error": str(exc)}, 400

        cache_set(uck, result, CACHE_UNKNOWNS_SEC)
        return result
