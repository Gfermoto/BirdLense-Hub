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
    mcp_token: str | None = None,
) -> dict[str, Any] | None:
    base = str(base_url or '').strip().rstrip('/')
    if not base:
        return None
    query = urlencode({'catalog': 'observed'})
    url = f'{base}/api/ui/migration-calendar/compare?{query}'
    req = Request(url, method='GET')
    key = str(api_key or '').strip()
    token = str(mcp_token or '').strip()
    if key:
        req.add_header('X-Birdlense-Api-Key', key)
    elif token:
        req.add_header('Authorization', f'Bearer {token}')
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


def _query_provider_bird_counts(conn: sqlite3.Connection, cutoff_iso: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT lower(COALESCE(vs.detection_provider, 'unknown')) AS provider, COUNT(*)
        FROM video_species vs
        JOIN video v ON v.id = vs.video_id
        JOIN species s ON s.id = vs.species_id
        WHERE v.deleted_at IS NULL
          AND COALESCE(v.start_time, '') >= ?
          AND lower(COALESCE(s.name, '')) NOT IN ('rodent', 'unknown', 'cat', 'dog', 'person')
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


def _query_frigate_hotspots(
    conn: sqlite3.Connection,
    cutoff_dt: datetime,
    *,
    head_limit: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='birdnet_fifo_event'"
    ).fetchall()
    if not table_rows:
        return {'by_camera': [], 'by_label': [], 'by_camera_label': []}

    cutoff_epoch = float(cutoff_dt.timestamp())
    try:
        by_camera = conn.execute(
            """
            SELECT
              lower(COALESCE(json_extract(payload, '$.camera'), 'unknown')) AS camera,
              COUNT(*) AS cnt
            FROM birdnet_fifo_event
            WHERE ts_epoch >= ?
              AND lower(COALESCE(json_extract(payload, '$.source'), '')) = 'frigate'
            GROUP BY lower(COALESCE(json_extract(payload, '$.camera'), 'unknown'))
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (cutoff_epoch, int(head_limit)),
        ).fetchall()
        by_label = conn.execute(
            """
            SELECT
              lower(
                COALESCE(
                  json_extract(payload, '$.label'),
                  json_extract(payload, '$.species'),
                  'unknown'
                )
              ) AS label,
              COUNT(*) AS cnt
            FROM birdnet_fifo_event
            WHERE ts_epoch >= ?
              AND lower(COALESCE(json_extract(payload, '$.source'), '')) = 'frigate'
            GROUP BY lower(
              COALESCE(
                json_extract(payload, '$.label'),
                json_extract(payload, '$.species'),
                'unknown'
              )
            )
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (cutoff_epoch, int(head_limit)),
        ).fetchall()
        by_camera_label = conn.execute(
            """
            SELECT
              lower(COALESCE(json_extract(payload, '$.camera'), 'unknown')) AS camera,
              lower(
                COALESCE(
                  json_extract(payload, '$.label'),
                  json_extract(payload, '$.species'),
                  'unknown'
                )
              ) AS label,
              COUNT(*) AS cnt
            FROM birdnet_fifo_event
            WHERE ts_epoch >= ?
              AND lower(COALESCE(json_extract(payload, '$.source'), '')) = 'frigate'
            GROUP BY
              lower(COALESCE(json_extract(payload, '$.camera'), 'unknown')),
              lower(
                COALESCE(
                  json_extract(payload, '$.label'),
                  json_extract(payload, '$.species'),
                  'unknown'
                )
              )
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (cutoff_epoch, int(head_limit)),
        ).fetchall()
    except sqlite3.Error:
        return {'by_camera': [], 'by_label': [], 'by_camera_label': []}

    return {
        'by_camera': [
            {'camera': str(camera or 'unknown'), 'count': _safe_int(cnt)}
            for camera, cnt in by_camera
        ],
        'by_label': [
            {'label': str(label or 'unknown'), 'count': _safe_int(cnt)}
            for label, cnt in by_label
        ],
        'by_camera_label': [
            {
                'camera': str(camera or 'unknown'),
                'label': str(label or 'unknown'),
                'count': _safe_int(cnt),
            }
            for camera, label, cnt in by_camera_label
        ],
    }


def _query_frigate_hotspots_from_decision_trace(
    conn: sqlite3.Connection,
    cutoff_iso: str,
    *,
    head_limit: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'"
    ).fetchall()
    if not table_rows:
        return {'by_camera': [], 'by_label': [], 'by_camera_label': []}

    rows = conn.execute(
        """
        SELECT data
        FROM activity_log
        WHERE type = 'decision_trace'
          AND COALESCE(created_at, '') >= ?
          AND data IS NOT NULL
          AND data != ''
        ORDER BY id DESC
        LIMIT 5000
        """,
        (cutoff_iso,),
    ).fetchall()
    if not rows:
        return {'by_camera': [], 'by_label': [], 'by_camera_label': []}

    by_camera: dict[str, int] = {}
    by_label: dict[str, int] = {}
    by_camera_label: dict[tuple[str, str], int] = {}
    for row in rows:
        raw = row[0] if row else None
        if not raw:
            continue
        try:
            payload = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        context = payload.get('recording_context') or {}
        camera = str(context.get('triggered_camera') or 'unknown').strip().lower() or 'unknown'
        tracks = payload.get('persisted_tracks') or []
        for track in tracks:
            provider = str(track.get('primary_provider') or track.get('detection_provider') or '').strip().lower()
            if provider != 'frigate':
                continue
            label = str(track.get('species_name') or track.get('label') or 'unknown').strip().lower() or 'unknown'
            by_camera[camera] = by_camera.get(camera, 0) + 1
            by_label[label] = by_label.get(label, 0) + 1
            key = (camera, label)
            by_camera_label[key] = by_camera_label.get(key, 0) + 1

    if not by_camera and not by_label:
        return {'by_camera': [], 'by_label': [], 'by_camera_label': []}

    top_camera = sorted(by_camera.items(), key=lambda x: (-x[1], x[0]))[: int(head_limit)]
    top_label = sorted(by_label.items(), key=lambda x: (-x[1], x[0]))[: int(head_limit)]
    top_camera_label = sorted(by_camera_label.items(), key=lambda x: (-x[1], x[0]))[: int(head_limit)]
    return {
        'by_camera': [{'camera': camera, 'count': int(cnt)} for camera, cnt in top_camera],
        'by_label': [{'label': label, 'count': int(cnt)} for label, cnt in top_label],
        'by_camera_label': [
            {'camera': camera, 'label': label, 'count': int(cnt)}
            for (camera, label), cnt in top_camera_label
        ],
    }


def _query_yolo_track_stats(
    conn: sqlite3.Connection,
    cutoff_iso: str,
    *,
    head_limit: int = 10,
) -> dict[str, Any]:
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'"
    ).fetchall()
    if not table_rows:
        return {
            'decision_trace_rows': 0,
            'yolo_ran_rows': 0,
            'yolo_track_found_rows': 0,
            'yolo_track_found_rate': None,
            'by_camera': [],
        }

    rows = conn.execute(
        """
        SELECT data
        FROM activity_log
        WHERE type = 'decision_trace'
          AND COALESCE(created_at, '') >= ?
          AND data IS NOT NULL
          AND data != ''
        ORDER BY id DESC
        LIMIT 5000
        """,
        (cutoff_iso,),
    ).fetchall()
    total = 0
    yolo_ran_total = 0
    yolo_found_total = 0
    by_camera: dict[str, dict[str, int]] = {}

    def _as_bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        raw = str(v or '').strip().lower()
        return raw in {'1', 'true', 'yes', 'on'}

    for row in rows:
        raw = row[0] if row else None
        if not raw:
            continue
        try:
            payload = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        total += 1
        context = payload.get('recording_context') or {}
        runtime = context.get('runtime_signals') or {}
        camera = str(context.get('triggered_camera') or 'unknown').strip().lower() or 'unknown'
        stats = by_camera.setdefault(camera, {'rows': 0, 'yolo_ran': 0, 'yolo_track_found': 0})
        stats['rows'] += 1
        yolo_ran = _as_bool(runtime.get('yolo_ran'))
        yolo_found = _as_bool(runtime.get('yolo_track_found'))
        if yolo_ran:
            yolo_ran_total += 1
            stats['yolo_ran'] += 1
        if yolo_found:
            yolo_found_total += 1
            stats['yolo_track_found'] += 1

    rate = (float(yolo_found_total) / float(total)) if total > 0 else None
    by_camera_rows = []
    for camera, stats in by_camera.items():
        rows_cnt = int(stats['rows'])
        found_cnt = int(stats['yolo_track_found'])
        by_camera_rows.append(
            {
                'camera': camera,
                'rows': rows_cnt,
                'yolo_ran': int(stats['yolo_ran']),
                'yolo_track_found': found_cnt,
                'yolo_track_found_rate': round(found_cnt / rows_cnt, 6) if rows_cnt > 0 else None,
            }
        )
    by_camera_rows.sort(
        key=lambda row: (
            row['yolo_track_found_rate'] if row['yolo_track_found_rate'] is not None else -1.0,
            -row['rows'],
            row['camera'],
        )
    )
    return {
        'decision_trace_rows': int(total),
        'yolo_ran_rows': int(yolo_ran_total),
        'yolo_track_found_rows': int(yolo_found_total),
        'yolo_track_found_rate': (round(rate, 6) if rate is not None else None),
        'by_camera': by_camera_rows[: int(head_limit)],
    }


def build_fusion_ab_report_from_db(
    *,
    db_path: str,
    days: int,
    min_yolo_share: float,
    min_yolo_share_bird_only: float,
    min_yolo_share_bird_only_warn: float,
    min_yolo_track_found_rate_warn: float,
    min_decision_trace_rows_warn: int,
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
        bird_provider_counts = _query_provider_bird_counts(conn, cutoff_iso)
        yolo_track_stats = _query_yolo_track_stats(conn, cutoff_iso)
        frigate_hotspots = _query_frigate_hotspots(conn, cutoff_dt)
        if (
            not frigate_hotspots.get('by_camera')
            and not frigate_hotspots.get('by_label')
            and not frigate_hotspots.get('by_camera_label')
        ):
            frigate_hotspots = _query_frigate_hotspots_from_decision_trace(
                conn,
                cutoff_iso,
            )
        duplicate_video_groups = _query_duplicate_video_groups(conn, cutoff_iso)
        duplicate_detection_groups = _query_duplicate_detection_groups(conn, cutoff_iso)
        generic_rows, generic_overlap_rows = _query_generic_overlap_counts(conn, cutoff_iso)
        if calendar_compare_totals is None:
            calendar_compare_totals = _query_calendar_totals_from_db(conn, cutoff_iso)
    finally:
        conn.close()

    yolo_rows = _safe_int(provider_counts.get('yolo'))
    frigate_rows = _safe_int(provider_counts.get('frigate'))
    yolo_bird_rows = _safe_int(bird_provider_counts.get('yolo'))
    frigate_bird_rows = _safe_int(bird_provider_counts.get('frigate'))
    total_rows = sum(_safe_int(v) for v in provider_counts.values())
    yolo_plus_frigate = yolo_rows + frigate_rows
    yolo_plus_frigate_bird_only = yolo_bird_rows + frigate_bird_rows
    yolo_share = (
        yolo_rows / yolo_plus_frigate if yolo_plus_frigate > 0 else None
    )
    yolo_share_bird_only = (
        yolo_bird_rows / yolo_plus_frigate_bird_only
        if yolo_plus_frigate_bird_only > 0
        else None
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
        'yolo_share_bird_only_ok': (
            bool(
                yolo_share_bird_only is not None
                and yolo_share_bird_only >= float(min_yolo_share_bird_only)
            )
            if yolo_plus_frigate_bird_only > 0
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
    warning_gates = {
        'yolo_share_bird_only_warn_ok': (
            bool(
                yolo_share_bird_only is not None
                and yolo_share_bird_only >= float(min_yolo_share_bird_only_warn)
            )
            if yolo_plus_frigate_bird_only > 0
            else False
        ),
    }
    recommendations: list[str] = []
    if not gates['yolo_share_ok']:
        recommendations.append(
            'yolo_share_low: tighten Frigate camera/label filters or raise trigger score; '
            'validate YOLO weights and confidence floors'
        )
    if not gates['yolo_share_bird_only_ok']:
        recommendations.append(
            'yolo_bird_share_low: calibrate bird-only detection balance (YOLO vs Frigate) '
            'without counting non-bird classes'
        )
    if not gates['duplicate_video_groups_ok'] or not gates['duplicate_detection_groups_ok']:
        recommendations.append(
            'dedupe_required: run dedupe_video_records and inspect ingest idempotency policy'
        )
    if not gates['generic_overlap_ok']:
        recommendations.append(
            'generic_overlap_high: tune absorb_generic_bird thresholds and arbitration conflict policy'
        )
    if not gates['calendar_delta_ratio_ok']:
        recommendations.append(
            'calendar_delta_high: reconcile species_visit derivation with calendar aggregation'
        )
    warnings: list[str] = []
    if not warning_gates['yolo_share_bird_only_warn_ok']:
        warnings.append(
            'yolo_bird_share_warn_low: bird-only YOLO share below warning threshold'
        )
    yolo_track_found_rate = yolo_track_stats.get('yolo_track_found_rate')
    if (
        yolo_track_found_rate is not None
        and float(yolo_track_found_rate) < float(min_yolo_track_found_rate_warn)
    ):
        warnings.append(
            'yolo_track_found_warn_low: YOLO tracks found too rarely in decision traces'
        )
    decision_trace_rows = _safe_int(yolo_track_stats.get('decision_trace_rows'))
    if decision_trace_rows < int(min_decision_trace_rows_warn):
        warnings.append(
            'decision_trace_sample_too_small: insufficient recent traces for stable KPI interpretation'
        )

    out = {
        'schema': 'fusion_ab_report@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'inputs': {
            'db_path': db_path,
            'days': int(days),
            'min_yolo_share': float(min_yolo_share),
            'min_yolo_share_bird_only': float(min_yolo_share_bird_only),
            'min_yolo_share_bird_only_warn': float(min_yolo_share_bird_only_warn),
            'min_yolo_track_found_rate_warn': float(min_yolo_track_found_rate_warn),
            'min_decision_trace_rows_warn': int(min_decision_trace_rows_warn),
            'max_duplicate_video_groups': int(max_duplicate_video_groups),
            'max_duplicate_detection_groups': int(max_duplicate_detection_groups),
            'max_generic_overlap_ratio': float(max_generic_overlap_ratio),
            'max_calendar_delta_ratio': float(max_calendar_delta_ratio),
        },
        'metrics': {
            'provider_counts': provider_counts,
            'bird_provider_counts': bird_provider_counts,
            'yolo_track_stats': yolo_track_stats,
            'frigate_hotspots': frigate_hotspots,
            'provider_total_rows': int(total_rows),
            'yolo_rows': int(yolo_rows),
            'frigate_rows': int(frigate_rows),
            'yolo_bird_rows': int(yolo_bird_rows),
            'frigate_bird_rows': int(frigate_bird_rows),
            'yolo_share_vs_frigate': (
                None if yolo_share is None else round(float(yolo_share), 6)
            ),
            'yolo_bird_share_vs_frigate': (
                None if yolo_share_bird_only is None else round(float(yolo_share_bird_only), 6)
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
        'warning_gates': warning_gates,
        'recommendations': recommendations,
        'warnings': warnings,
        'ok': all(bool(v) for v in gates.values()),
    }
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--base-url', default='', help='Optional base URL for /api/ui/migration-calendar/compare')
    parser.add_argument('--api-key', default='', help='Optional X-Birdlense-Api-Key for protected UI API')
    parser.add_argument('--mcp-token', default='', help='Optional MCP bearer token for protected UI API')
    parser.add_argument('--api-timeout-seconds', type=float, default=8.0)
    parser.add_argument('--min-yolo-share', type=float, default=0.30)
    parser.add_argument('--min-yolo-share-bird-only', type=float, default=0.30)
    parser.add_argument('--min-yolo-share-bird-only-warn', type=float, default=0.15)
    parser.add_argument('--min-yolo-track-found-rate-warn', type=float, default=0.40)
    parser.add_argument('--min-decision-trace-rows-warn', type=int, default=20)
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
                mcp_token=str(args.mcp_token or ''),
            )
        except Exception as exc:  # pragma: no cover - network/env dependent
            api_error = str(exc)

    out = build_fusion_ab_report_from_db(
        db_path=str(args.db),
        days=max(1, int(args.days)),
        min_yolo_share=float(args.min_yolo_share),
        min_yolo_share_bird_only=float(args.min_yolo_share_bird_only),
        min_yolo_share_bird_only_warn=float(args.min_yolo_share_bird_only_warn),
        min_yolo_track_found_rate_warn=float(args.min_yolo_track_found_rate_warn),
        min_decision_trace_rows_warn=max(0, int(args.min_decision_trace_rows_warn)),
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
            out['notes'] = [
                *list(out.get('notes') or []),
                f'calendar_compare_fetch_failed_fallback_db: {api_error}',
            ]
        else:
            out['warnings'] = [
                *list(out.get('warnings') or []),
                f'calendar_compare_fetch_failed: {api_error}',
            ]
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get('ok')) else 3


if __name__ == '__main__':
    raise SystemExit(main())

