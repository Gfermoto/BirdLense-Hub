"""Парсинг окна для GET /api/ui/report/pdf (#293)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from util import parse_utc_timestamp

MAX_REPORT_RANGE_DAYS = 93


class MonthlyReportWindowError(ValueError):
    """Некорректные month= или start_time/end_time."""


def resolve_monthly_report_window(
    month_param: str | None,
    start_param: str | None,
    end_param: str | None,
) -> tuple[datetime, datetime, str]:
    """(start_dt, end_dt, month_label). Naive UTC для границ месяца/интервала."""
    if month_param:
        try:
            year, month = map(int, month_param.split("-"))
            start_dt = datetime(
                year,
                month,
                1,
                0,
                0,
                0,
                tzinfo=timezone.utc,
            ).replace(tzinfo=None)
            if month == 12:
                end_dt = datetime(
                    year + 1,
                    1,
                    1,
                    0,
                    0,
                    0,
                    tzinfo=timezone.utc,
                ).replace(tzinfo=None) - timedelta(seconds=1)
            else:
                end_dt = datetime(
                    year,
                    month + 1,
                    1,
                    0,
                    0,
                    0,
                    tzinfo=timezone.utc,
                ).replace(tzinfo=None) - timedelta(seconds=1)
            month_label = start_dt.strftime("%B %Y")
        except (ValueError, IndexError) as exc:
            raise MonthlyReportWindowError(
                "Invalid month format. Use YYYY-MM",
            ) from exc
        return start_dt, end_dt, month_label

    if start_param and end_param:
        try:
            start_dt = parse_utc_timestamp(start_param)
            end_dt = parse_utc_timestamp(end_param)
        except ValueError as exc:
            raise MonthlyReportWindowError("Invalid datetime format") from exc
        if end_dt - start_dt > timedelta(days=MAX_REPORT_RANGE_DAYS):
            raise MonthlyReportWindowError("Interval must not exceed 3 months")
        month_label = f"{start_dt.strftime('%Y-%m-%d')} — {end_dt.strftime('%Y-%m-%d')}"
        return start_dt, end_dt, month_label

    raise MonthlyReportWindowError(
        "Provide month=YYYY-MM or start_time and end_time",
    )
