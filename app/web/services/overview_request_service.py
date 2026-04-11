"""Парсинг окна дат для GET /api/ui/overview (#293)."""
from __future__ import annotations

from datetime import datetime, timezone

from util import observer_local_day_bounds, parse_utc_timestamp


class OverviewWindowError(ValueError):
    """Некорректные query-параметры overview."""


def resolve_overview_window(
    date_param: str | None,
    start_time_param: str | None,
    end_time_param: str | None,
) -> tuple[datetime, datetime]:
    """Границы дня/интервала (naive UTC, как в роутере)."""
    try:
        if date_param:
            return observer_local_day_bounds(date_param)
        if start_time_param and end_time_param:
            return (
                parse_utc_timestamp(start_time_param),
                parse_utc_timestamp(end_time_param),
            )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(
            hour=23, minute=59, second=59, microsecond=999999,
        )
        return start_of_day, end_of_day
    except (ValueError, TypeError) as exc:
        raise OverviewWindowError('Invalid timestamp format.') from exc
