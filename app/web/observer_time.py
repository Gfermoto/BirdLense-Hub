"""Часовой пояс наблюдателя, локальные сутки/интервалы, солнце (#222, было в util.py)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from app_config.app_config import app_config
from time_util import ensure_utc
from weather_service import _normalize_coord


def fetch_sun_times(date_str: str) -> dict | None:
    """Sun times for date at configured location, or None if coords missing."""
    from datetime import date

    lat = _normalize_coord(app_config.get("secrets.latitude"))
    lon = _normalize_coord(app_config.get("secrets.longitude"))
    if not lat or not lon:
        return None
    try:
        lat_f = float(str(lat).replace(",", "."))
        lon_f = float(str(lon).replace(",", "."))
    except (ValueError, TypeError):
        return None
    try:
        year, month, day = map(int, date_str.split("-"))
        d = date(year, month, day)
    except (ValueError, TypeError):
        return None
    try:
        from astral import LocationInfo
        from astral.sun import sun
        import zoneinfo

        tz = zoneinfo.ZoneInfo("UTC")
        loc = LocationInfo("", "", "UTC", lat_f, lon_f)
        s = sun(loc.observer, date=d, tzinfo=tz)
        return {
            "dawn": s["dawn"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sunrise": s["sunrise"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "noon": s["noon"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sunset": s["sunset"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dusk": s["dusk"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as e:
        logging.warning("Sun times calculation failed: %s", e)
        return None


@lru_cache(maxsize=32)
def _observer_timezone_name_cached(lat: str, lon: str) -> str:
    import zoneinfo
    from timezonefinder import TimezoneFinder

    try:
        lat_f = float(str(lat).replace(",", "."))
        lon_f = float(str(lon).replace(",", "."))
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat_f, lng=lon_f) or "UTC"
        zoneinfo.ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return "UTC"


def get_observer_timezone_name() -> str:
    """IANA timezone name from configured lat/lon, or UTC."""
    lat = _normalize_coord(app_config.get("secrets.latitude"))
    lon = _normalize_coord(app_config.get("secrets.longitude"))
    if not lat or not lon:
        return "UTC"
    return _observer_timezone_name_cached(str(lat), str(lon))


def get_observer_timezone():
    """ZoneInfo for observer (or UTC fallback)."""
    import zoneinfo

    try:
        return zoneinfo.ZoneInfo(get_observer_timezone_name())
    except Exception:
        return timezone.utc


def observer_local_day_bounds(date_str: str) -> tuple[datetime, datetime]:
    """UTC naive (start, end) for the observer-local calendar day date_str."""
    local_day = datetime.strptime(date_str, "%Y-%m-%d")
    tz = get_observer_timezone()
    start_local = local_day.replace(tzinfo=tz)
    end_local = start_local + timedelta(days=1) - timedelta(microseconds=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def observer_local_range(
    date_str: str,
    *,
    time_of_day: str = "all",
    hour: int | None = None,
) -> tuple[datetime, datetime]:
    """UTC naive bounds for a slot on date_str (hour, time_of_day, or full day)."""
    local_day = datetime.strptime(date_str, "%Y-%m-%d")
    tz = get_observer_timezone()
    start_local = local_day.replace(tzinfo=tz)

    if hour is not None:
        if hour < 0 or hour > 23:
            raise ValueError("hour must be in range 0..23")
        range_start = start_local.replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        range_end = start_local.replace(
            hour=hour,
            minute=59,
            second=59,
            microsecond=999999,
        )
    elif time_of_day == "all":
        range_start = start_local.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        range_end = start_local.replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )
    else:
        ranges = {
            "night": (0, 6),
            "morning": (6, 10),
            "day": (10, 14),
            "afternoon": (14, 18),
            "evening": (18, 24),
        }
        if time_of_day not in ranges:
            raise ValueError("invalid time_of_day")
        start_hour, end_hour = ranges[time_of_day]
        range_start = start_local.replace(
            hour=start_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        if end_hour >= 24:
            range_end = start_local.replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999,
            )
        else:
            range_end = start_local.replace(
                hour=end_hour,
                minute=0,
                second=0,
                microsecond=0,
            ) - timedelta(microseconds=1)

    return (
        range_start.astimezone(timezone.utc).replace(tzinfo=None),
        range_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def observer_local_hour(dt: datetime | None) -> int:
    """Hour 0..23 in observer local time for UTC-aware dt."""
    if dt is None:
        return 0
    local = ensure_utc(dt).astimezone(get_observer_timezone())
    return int(local.hour)
