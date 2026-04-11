"""Табличные строки для экспорта timeline (CSV / JSON / eBird) (#293)."""
from __future__ import annotations

from datetime import timezone

from time_util import parse_timeline_iso


def build_timeline_export_rows(merged: list) -> list[dict]:
    """Плоские dict-строки из merged timeline items (как в /timeline/export)."""
    rows = []
    for item in merged:
        st_p = parse_timeline_iso(item['start_time'])
        et_p = parse_timeline_iso(item['end_time'])
        duration = max(0, round((et_p - st_p).total_seconds()))
        w = item.get('weather') or {}
        rows.append({
            'id': item['id'],
            'species_name': item['species']['name'],
            'start_time': st_p.astimezone(timezone.utc).isoformat(),
            'end_time': et_p.astimezone(timezone.utc).isoformat(),
            'duration_sec': duration,
            'max_simultaneous': item.get('max_simultaneous', 1),
            'detection_count': len(item.get('detections') or []),
            'temp': w.get('temp'),
            'clouds': w.get('clouds'),
        })
    return rows
