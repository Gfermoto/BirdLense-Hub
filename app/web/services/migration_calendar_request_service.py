"""Валидация query для /api/ui/migration-calendar (#293)."""

from __future__ import annotations

import re

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ALLOWED_CATALOGS = frozenset(
    {
        "observed",
        "dataset",
        "full_eu",
        "active",
        "full",
    }
)
_ALLOWED_METRICS = frozenset({'encounters', 'visits', 'max_simultaneous'})


def validate_migration_calendar_params(
    catalog: str,
    start_date: str | None,
    end_date: str | None,
    metric: str = 'encounters',
) -> str | None:
    """None если ок, иначе текст error для API."""
    if catalog not in _ALLOWED_CATALOGS:
        return "catalog must be observed, dataset or full_eu"
    if metric not in _ALLOWED_METRICS:
        return 'metric must be encounters, visits or max_simultaneous'
    if start_date and not _ISO_DATE.match(start_date):
        return "start_date must be YYYY-MM-DD"
    if end_date and not _ISO_DATE.match(end_date):
        return "end_date must be YYYY-MM-DD"
    if start_date and end_date and start_date > end_date:
        return "start_date must be <= end_date"
    return None


def migration_calendar_cache_key(
    start_year: int | None,
    end_year: int | None,
    start_date: str | None,
    end_date: str | None,
    catalog: str,
    evidence: str = "all",
    metric: str = 'encounters',
) -> str:
    return (
        'migration_cal:v5:'
        f'{start_year}:{end_year}:{start_date}:{end_date}:{catalog}:{evidence}:{metric}'
    )
