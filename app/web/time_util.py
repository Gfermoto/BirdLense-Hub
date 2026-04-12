"""Naive/aware UTC helpers for DB and API (#222)."""

from __future__ import annotations

from datetime import datetime, timezone


def ensure_utc(dt: datetime) -> datetime:
    """Timezone-aware UTC. SQLite often returns naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_utc_timestamp(param) -> datetime:
    """Unix sec → naive UTC datetime (tzinfo=None). Raises ValueError.

    Для SQLite и сравнений с naive полями БД. Нужен aware UTC — см. ``ensure_utc``.
    """
    if param is None:
        raise ValueError("Timestamp is required")
    ts = int(param)
    if not (0 <= ts <= 2147483647):
        raise ValueError("Timestamp out of range")
    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)


def parse_timeline_iso(s: str) -> datetime:
    """ISO string from timeline payloads (Z suffix → UTC)."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d
