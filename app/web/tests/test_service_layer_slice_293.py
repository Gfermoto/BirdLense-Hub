"""Юнит-тесты сервисов, вынесенных из ui_overview_timeline_routes (#293)."""

from datetime import datetime, timedelta, timezone

import pytest


def test_validate_migration_calendar_params_ok_and_errors():
    from services.migration_calendar_request_service import (
        validate_migration_calendar_params,
    )

    assert validate_migration_calendar_params('observed', None, None) is None
    assert validate_migration_calendar_params('active', '2024-01-01', '2024-01-31') is None
    err = validate_migration_calendar_params('nope', None, None)
    assert err and 'catalog' in err
    err = validate_migration_calendar_params('observed', '2024/01/01', None)
    assert 'start_date' in err
    err = validate_migration_calendar_params('observed', '2024-02-01', '2024-01-01')
    assert 'start_date must be <=' in err


def test_migration_calendar_cache_key_stable():
    from services.migration_calendar_request_service import migration_calendar_cache_key

    k = migration_calendar_cache_key(2024, 2025, None, None, 'dataset', 'all')
    assert k == 'migration_cal:v3:2024:2025:None:None:dataset:all'


def test_validate_timeline_export_format():
    from services.timeline_export_service import validate_timeline_export_format

    assert validate_timeline_export_format('json') is None
    assert validate_timeline_export_format('xml') is not None


def test_resolve_timeline_utc_window_unix_range():
    from services.timeline_window_service import resolve_timeline_utc_window

    ts0 = int(datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    ts1 = int(datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc).timestamp())
    start_dt, end_dt = resolve_timeline_utc_window(
        date_param=None,
        time_of_day='all',
        hour_param=None,
        start_time=str(ts0),
        end_time=str(ts1),
    )
    assert start_dt < end_dt


def test_resolve_timeline_utc_window_requires_both_timestamps():
    from services.timeline_window_service import (
        TimelineWindowError,
        resolve_timeline_utc_window,
    )

    with pytest.raises(TimelineWindowError, match='Both start_time'):
        resolve_timeline_utc_window(
            date_param=None,
            time_of_day='all',
            hour_param=None,
            start_time='123',
            end_time=None,
        )


def test_resolve_monthly_report_window_month():
    from services.monthly_report_window_service import resolve_monthly_report_window

    start_dt, end_dt, label = resolve_monthly_report_window('2026-03', None, None)
    assert start_dt.year == 2026 and start_dt.month == 3 and start_dt.day == 1
    assert end_dt.month == 3 and end_dt >= start_dt
    assert '2026' in label


def test_resolve_monthly_report_window_rejects_long_range():
    from services.monthly_report_window_service import (
        MAX_REPORT_RANGE_DAYS,
        MonthlyReportWindowError,
        resolve_monthly_report_window,
    )

    t0 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    t1 = int(
        (
            datetime(2026, 1, 1, tzinfo=timezone.utc)
            + timedelta(days=MAX_REPORT_RANGE_DAYS + 1)
        ).timestamp(),
    )
    with pytest.raises(MonthlyReportWindowError, match='3 months'):
        resolve_monthly_report_window(None, str(t0), str(t1))


def test_build_timeline_export_response_json_and_empty_csv():
    from services.timeline_export_service import build_timeline_export_response_parts

    start = datetime(2026, 3, 24, 0, 0, 0)
    end = datetime(2026, 3, 24, 23, 0, 0)
    rows = [
        {
            'id': 1,
            'species_name': 'Test Bird',
            'start_time': '2026-03-24T10:00:00+00:00',
            'end_time': '2026-03-24T10:00:05+00:00',
            'duration_sec': 5,
            'max_simultaneous': 1,
            'detection_count': 0,
            'temp': None,
            'clouds': None,
        },
    ]
    body, mime, headers = build_timeline_export_response_parts(
        'json', rows, start, end,
    )
    assert mime == 'application/json'
    assert 'Test Bird' in body
    assert 'birdlense_timeline.json' in headers['Content-Disposition']

    body_csv, mime_csv, _ = build_timeline_export_response_parts(
        'csv', [], start, end,
    )
    assert mime_csv == 'text/csv'
    assert 'species_name' in body_csv


def test_build_timeline_export_response_ebird(monkeypatch):
    from services import timeline_export_service as tes

    monkeypatch.setattr(
        tes,
        'build_ebird_csv',
        lambda rows, _s, _e: 'stub,' + str(len(rows)),
    )
    body, mime, headers = tes.build_timeline_export_response_parts(
        'ebird',
        [
            {'species_name': 'A', 'x': 1},
            {'species_name': 'A', 'x': 2},
            {'species_name': 'B', 'x': 3},
        ],
        datetime(2026, 1, 1),
        datetime(2026, 1, 2),
    )
    assert mime == 'text/csv'
    assert body == 'stub,2'
    assert 'ebird' in headers['Content-Disposition']
