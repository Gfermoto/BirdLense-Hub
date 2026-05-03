#!/usr/bin/env python3
"""Build fusion_ab_report@v1 from SQLite + optional API compare totals."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _fetch_calendar_compare_totals(
    base_url: str,
    timeout_seconds: float = 8.0,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    base = str(base_url or '').strip().rstrip('/')
    if not base:
        return None
    query = urlencode({'catalog': 'observed'})
    url = f'{base}/api/ui/migration-calendar/compare?{query}'
    req = Request(url, method='GET')
    if str(api_key or '').strip():
        req.add_header('X-API-Key', str(api_key).strip())
    with urlopen(req, timeout=float(timeout_seconds)) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    totals = (payload or {}).get('totals') or {}
    return {
        'encounters': _safe_int(totals.get('encounters')),
        'max_simultaneous': _safe_int(totals.get('max_simultaneous')),
        'delta': _safe_int(totals.get('delta')),
    }


def _query_provider_counts(conn: sqlite3.Connection, cutoff_iso: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT lower(COALESCE(vs.detection_provider, 'unknown')) AS provider, COUNT(*)
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        WHERE v.deleted_at IS NULL
          AND COALESCE(v.start_time, '') >= ?
        GROUP BY lower(COALESCE(vs.detection_provider, 'unknown'))
        """,
        (cutoff_iso,),
    ).fetchall()
    out: dict[str, int] = {}
    for provider, cnt in rows:
        key = str(provider or 'unknown').strip().lower() or 'unknown'
        out[key] = _safe_int(cnt)
    return out


def _query_duplicate_video_groups(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT v.video_path, v.start_time, v.end_time, v.processor_version, COUNT(*) AS c
          FROM video v
          WHERE v.deleted_at IS NULL
            AND COALESCE(v.start_time, '') >= ?
          GROUP BY v.video_path, v.start_time, v.end_time, v.processor_version
          HAVING c > 1
        ) q
        """,
        (cutoff_iso,),
    ).fetchone()
    return _safe_int((row or [0])[0])


def _query_duplicate_detection_groups(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT
            vs.video_id,
            vs.species_id,
            vs.start_time,
            vs.end_time,
            vs.confidence,
            COALESCE(vs.track_id, -1),
            COALESCE(vs.detection_provider, ''),
            COALESCE(vs.source, ''),
            COUNT(*) AS c
          FROM video_species vs
          WHERE COALESCE(vs.created_at, '') >= ?
          GROUP BY
            vs.video_id,
            vs.species_id,
            vs.start_time,
            vs.end_time,
            vs.confidence,
            COALESCE(vs.track_id, -1),
            COALESCE(vs.detection_provider, ''),
            COALESCE(vs.source, '')
          HAVING c > 1
        ) q
        """,
        (cutoff_iso,),
    ).fetchone()
    return _safe_int((row or [0])[0])


def _query_generic_overlap_counts(conn: sqlite3.Connection, cutoff_iso: str) -> tuple[int, int]:
    generic_rows = _safe_int(
        (
            conn.execute(
                """
                SELECT COUNT(*)
                FROM video_species vs
                JOIN species s ON s.id = vs.species_id
                WHERE lower(COALESCE(s.name, '')) = 'bird'
                  AND COALESCE(vs.created_at, '') >= ?
                """,
                (cutoff_iso,),
            ).fetchone()
            or [0]
        )[0]
    )
    overlap_rows = _safe_int(
        (
            conn.execute(
                """
                SELECT COUNT(DISTINCT b.id)
                FROM video_species b
                JOIN species sb ON sb.id = b.species_id
                JOIN video_species s ON s.video_id = b.video_id
                JOIN species ss ON ss.id = s.species_id
                WHERE lower(COALESCE(sb.name, '')) = 'bird'
                  AND lower(COALESCE(ss.name, '')) != 'bird'
                  AND s.start_time <= b.end_time
                  AND s.end_time >= b.start_time
                  AND COALESCE(b.created_at, '') >= ?
                """,
                (cutoff_iso,),
            ).fetchone()
            or [0]
        )[0]
    )
    return generic_rows, overlap_rows


def _query_calendar_totals_from_db(
    conn: sqlite3.Connection,
    cutoff_iso: str,
) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
          COUNT(sv.id) AS encounters_total,
          COALESCE(SUM(sv.max_simultaneous), 0) AS max_sim_total
        FROM species_visit sv
        JOIN species s ON s.id = sv.species_id
        WHERE lower(COALESCE(s.name, '')) != 'bird'
          AND COALESCE(sv.start_time, '') >= ?
        """,
        (cutoff_iso,),
    ).fetchone()
    encounters = _safe_int((row or [0, 0])[0])
    max_simultaneous = _safe_int((row or [0, 0])[1])
    return {
        'encounters': encounters,
        'max_simultaneous': max_simultaneous,
        'delta': int(max_simultaneous - encounters),
    }


def build_fusion_ab_report_from_db(
    *,
    db_path: str,
    days: int,
    min_yolo_share: float,
    max_duplicate_video_groups: int,
    max_duplicate_detection_groups: int,
    max_generic_overlap_ratio: float,
    max_calendar_delta_ratio: float,
    calendar_compare_totals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
    cutoff_iso = cutoff_dt.isoformat()
    conn = sqlite3.connect(db_path)
    calendar_totals_source = 'api' if calendar_compare_totals is not None else 'db'
    try:
        provider_counts = _query_provider_counts(conn, cutoff_iso)
        duplicate_video_groups = _query_duplicate_video_groups(conn, cutoff_iso)
        duplicate_detection_groups = _query_duplicate_detection_groups(conn, cutoff_iso)
        generic_rows, generic_overlap_rows = _query_generic_overlap_counts(conn, cutoff_iso)
        if calendar_compare_totals is None:
            calendar_compare_totals = _query_calendar_totals_from_db(conn, cutoff_iso)
    finally:
        conn.close()

    yolo_rows = _safe_int(provider_counts.get('yolo'))
    frigate_rows = _safe_int(provider_counts.get('frigate'))
    total_rows = sum(_safe_int(v) for v in provider_counts.values())
    yolo_plus_frigate = yolo_rows + frigate_rows
    yolo_share = (
        yolo_rows / yolo_plus_frigate if yolo_plus_frigate > 0 else None
    )
    generic_overlap_ratio = (
        generic_overlap_rows / generic_rows if generic_rows > 0 else 0.0
    )

    encounters = None
    max_simultaneous = None
    calendar_delta = None
    calendar_delta_ratio = None
    if calendar_compare_totals is not None:
        encounters = _safe_int(calendar_compare_totals.get('encounters'))
        max_simultaneous = _safe_int(calendar_compare_totals.get('max_simultaneous'))
        calendar_delta = _safe_int(calendar_compare_totals.get('delta'))
        if encounters > 0:
            calendar_delta_ratio = abs(float(calendar_delta)) / float(encounters)

    gates = {
        'yolo_share_ok': (
            bool(yolo_share is not None and yolo_share >= float(min_yolo_share))
            if yolo_plus_frigate > 0
            else False
        ),
        'duplicate_video_groups_ok': bool(
            int(duplicate_video_groups) <= int(max_duplicate_video_groups)
        ),
        'duplicate_detection_groups_ok': bool(
            int(duplicate_detection_groups) <= int(max_duplicate_detection_groups)
        ),
        'generic_overlap_ok': bool(
            float(generic_overlap_ratio) <= float(max_generic_overlap_ratio)
        ),
        'calendar_delta_ratio_ok': (
            True
            if calendar_delta_ratio is None
            else bool(float(calendar_delta_ratio) <= float(max_calendar_delta_ratio))
        ),
    }

    out = {
        'schema': 'fusion_ab_report@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'inputs': {
            'db_path': db_path,
            'days': int(days),
            'min_yolo_share': float(min_yolo_share),
            'max_duplicate_video_groups': int(max_duplicate_video_groups),
            'max_duplicate_detection_groups': int(max_duplicate_detection_groups),
            'max_generic_overlap_ratio': float(max_generic_overlap_ratio),
            'max_calendar_delta_ratio': float(max_calendar_delta_ratio),
        },
        'metrics': {
            'provider_counts': provider_counts,
            'provider_total_rows': int(total_rows),
            'yolo_rows': int(yolo_rows),
            'frigate_rows': int(frigate_rows),
            'yolo_share_vs_frigate': (
                None if yolo_share is None else round(float(yolo_share), 6)
            ),
            'duplicate_video_groups': int(duplicate_video_groups),
            'duplicate_detection_groups': int(duplicate_detection_groups),
            'generic_bird_rows': int(generic_rows),
            'generic_bird_overlap_rows': int(generic_overlap_rows),
            'generic_bird_overlap_ratio': round(float(generic_overlap_ratio), 6),
            'calendar_compare_totals': {
                'encounters': encounters,
                'max_simultaneous': max_simultaneous,
                'delta': calendar_delta,
                'source': calendar_totals_source,
                'delta_ratio_abs_vs_encounters': (
                    None
                    if calendar_delta_ratio is None
                    else round(float(calendar_delta_ratio), 6)
                ),
            },
        },
        'gates': gates,
        'ok': all(bool(v) for v in gates.values()),
    }
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--base-url', default='', help='Optional base URL for /api/ui/migration-calendar/compare')
    parser.add_argument('--api-key', default='', help='Optional X-API-Key for protected UI API')
    parser.add_argument('--api-timeout-seconds', type=float, default=8.0)
    parser.add_argument('--min-yolo-share', type=float, default=0.30)
    parser.add_argument('--max-duplicate-video-groups', type=int, default=0)
    parser.add_argument('--max-duplicate-detection-groups', type=int, default=0)
    parser.add_argument('--max-generic-overlap-ratio', type=float, default=0.60)
    parser.add_argument('--max-calendar-delta-ratio', type=float, default=5.00)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    api_error = None
    compare_totals = None
    if str(args.base_url or '').strip():
        try:
            compare_totals = _fetch_calendar_compare_totals(
                str(args.base_url),
                timeout_seconds=float(args.api_timeout_seconds),
                api_key=str(args.api_key or ''),
            )
        except Exception as exc:  # pragma: no cover - network/env dependent
            api_error = str(exc)

    out = build_fusion_ab_report_from_db(
        db_path=str(args.db),
        days=max(1, int(args.days)),
        min_yolo_share=float(args.min_yolo_share),
        max_duplicate_video_groups=max(0, int(args.max_duplicate_video_groups)),
        max_duplicate_detection_groups=max(0, int(args.max_duplicate_detection_groups)),
        max_generic_overlap_ratio=max(0.0, float(args.max_generic_overlap_ratio)),
        max_calendar_delta_ratio=max(0.0, float(args.max_calendar_delta_ratio)),
        calendar_compare_totals=compare_totals,
    )
    if api_error:
        totals_src = (
            (out.get('metrics') or {})
            .get('calendar_compare_totals', {})
            .get('source')
        )
        if totals_src == 'db':
            out['notes'] = [f'calendar_compare_fetch_failed_fallback_db: {api_error}']
        else:
            out['warnings'] = [f'calendar_compare_fetch_failed: {api_error}']
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get('ok')) else 3


if __name__ == '__main__':
    raise SystemExit(main())

