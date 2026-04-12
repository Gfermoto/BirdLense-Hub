"""Парсинг окна дат/времени для /api/ui/timeline и export (#293)."""

from __future__ import annotations

from datetime import datetime

from util import observer_local_range, parse_utc_timestamp


class TimelineWindowError(ValueError):
    """Некорректные параметры окна (сообщение — тело error для API)."""


def resolve_timeline_utc_window(
    *,
    date_param: str | None,
    time_of_day: str,
    hour_param: int | None,
    start_time: str | None,
    end_time: str | None,
) -> tuple[datetime, datetime]:
    """Naive UTC границы окна (как раньше в роутерах)."""
    if date_param:
        try:
            return observer_local_range(
                date_param,
                time_of_day=time_of_day,
                hour=hour_param,
            )
        except ValueError as exc:
            raise TimelineWindowError("Invalid local date range parameters") from exc
    if not start_time or not end_time:
        raise TimelineWindowError("Both start_time and end_time are required")
    try:
        start_dt = parse_utc_timestamp(start_time)
        end_dt = parse_utc_timestamp(end_time)
    except ValueError as exc:
        raise TimelineWindowError("Invalid datetime format") from exc
    return start_dt, end_dt
