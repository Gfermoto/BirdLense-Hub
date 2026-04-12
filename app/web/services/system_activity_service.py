"""Агрегация uptime по дням для GET /api/ui/system/activity (#293)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from models import ActivityLog


class SystemActivityMonthError(ValueError):
    """Некорректный query month=YYYY-MM."""


def parse_system_activity_month(month: str | None) -> tuple[datetime, datetime]:
    """(start_date inclusive, end_date exclusive) для фильтра по heartbeat."""
    m = month or datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        start_date = datetime.strptime(m, "%Y-%m")
    except ValueError as exc:
        raise SystemActivityMonthError(
            "Invalid month format, use YYYY-MM",
        ) from exc
    if not (2020 <= start_date.year <= 2030 and 1 <= start_date.month <= 12):
        raise SystemActivityMonthError("Invalid month format, use YYYY-MM")
    end_date = (start_date.replace(day=1) + timedelta(days=32)).replace(day=1)
    return start_date, end_date


def fetch_system_activity_daily_uptime(
    session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    activities = (
        session.query(
            func.strftime("%Y-%m-%d", ActivityLog.created_at).label("date"),
            func.sum(
                func.strftime("%s", ActivityLog.updated_at) - func.strftime("%s", ActivityLog.created_at),
            ).label("total_uptime"),
        )
        .filter(
            ActivityLog.type == "heartbeat",
            ActivityLog.created_at >= start_date,
            ActivityLog.created_at < end_date,
        )
        .group_by(func.strftime("%Y-%m-%d", ActivityLog.created_at))
        .all()
    )
    return [
        {
            "date": day,
            "totalUptime": round(duration / 3600, 1) if duration else 0,
        }
        for day, duration in activities
    ]
