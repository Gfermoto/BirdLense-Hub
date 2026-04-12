"""Табличные строки и тело ответа для /api/ui/timeline/export (#293)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from time_util import parse_timeline_iso

from services.ebird_export_service import build_ebird_csv

_TIMELINE_EXPORT_FORMATS = frozenset({"csv", "json", "ebird"})
_CSV_COLUMNS = [
    "id",
    "species_name",
    "start_time",
    "end_time",
    "duration_sec",
    "max_simultaneous",
    "detection_count",
    "temp",
    "clouds",
]


def validate_timeline_export_format(fmt: str) -> str | None:
    """None если ок, иначе текст error для JSON 400."""
    if fmt not in _TIMELINE_EXPORT_FORMATS:
        return "format must be csv, json, or ebird"
    return None


def build_timeline_export_rows(merged: list) -> list[dict]:
    """Плоские dict-строки из merged timeline items (как в /timeline/export)."""
    rows = []
    for item in merged:
        st_p = parse_timeline_iso(item["start_time"])
        et_p = parse_timeline_iso(item["end_time"])
        duration = max(0, round((et_p - st_p).total_seconds()))
        w = item.get("weather") or {}
        rows.append(
            {
                "id": item["id"],
                "species_name": item["species"]["name"],
                "start_time": st_p.astimezone(timezone.utc).isoformat(),
                "end_time": et_p.astimezone(timezone.utc).isoformat(),
                "duration_sec": duration,
                "max_simultaneous": item.get("max_simultaneous", 1),
                "detection_count": len(item.get("detections") or []),
                "temp": w.get("temp"),
                "clouds": w.get("clouds"),
            }
        )
    return rows


def _ebird_dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        name = r.get("species_name", "")
        if name and name not in seen:
            seen.add(name)
            out.append(r)
    return out


def build_timeline_export_response_parts(
    fmt: str,
    rows: list[dict],
    start_dt: datetime,
    end_dt: datetime,
) -> tuple[str, str, dict[str, str]]:
    """Тело ответа, mimetype, заголовки (без Flask Response)."""
    if fmt == "ebird":
        body = build_ebird_csv(_ebird_dedupe_rows(rows), start_dt, end_dt)
        return (
            body,
            "text/csv",
            {"Content-Disposition": "attachment; filename=birdlense_ebird.csv"},
        )
    if fmt == "json":
        body = json.dumps(rows, ensure_ascii=False, indent=2)
        return (
            body,
            "application/json",
            {"Content-Disposition": "attachment; filename=birdlense_timeline.json"},
        )
    output = io.StringIO()
    writer = csv.writer(output)
    if not rows:
        writer.writerow(_CSV_COLUMNS)
    else:
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow(r.values())
    return (
        output.getvalue(),
        "text/csv",
        {"Content-Disposition": "attachment; filename=birdlense_timeline.csv"},
    )
