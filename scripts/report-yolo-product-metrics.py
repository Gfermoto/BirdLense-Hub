#!/usr/bin/env python3
"""Summarize YOLO-first product metrics from decision_trace activity logs."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter


def _load_latest_traces(db_path: str) -> tuple[dict[int, dict], dict[int, dict]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT data FROM activity_log WHERE type = 'decision_trace' ORDER BY id ASC",
        ).fetchall()
    finally:
        conn.close()
    latest_live: dict[int, dict] = {}
    latest_regen: dict[int, dict] = {}
    for (raw,) in rows:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        video_id = payload.get('video_id')
        if video_id is None:
            continue
        triggered_by = (
            (payload.get('recording_context') or {}).get('triggered_by')
            or 'live'
        )
        if triggered_by == 'track_regen':
            latest_regen[int(video_id)] = payload
        else:
            latest_live[int(video_id)] = payload
    return latest_live, latest_regen


def _iter_persisted_tracks(traces: dict[int, dict]):
    for payload in traces.values():
        for track in payload.get('persisted_tracks') or payload.get('accepted_tracks') or []:
            yield track


def _species_signature(payload: dict) -> tuple[tuple[str, str], ...]:
    rows = []
    for track in payload.get('persisted_tracks') or payload.get('accepted_tracks') or []:
        rows.append(
            (
                str(track.get('species_name') or ''),
                str(track.get('decision_kind') or ''),
            ),
        )
    return tuple(sorted(rows))


def _dataset_export_failures(dataset_info_path: str | None) -> dict:
    if not dataset_info_path:
        return {
            'provided': False,
            'duplicate_track_count': None,
            'group_or_video_leakage_count': None,
            'failed': None,
        }
    payload = json.loads(open(dataset_info_path, 'r', encoding='utf-8').read())
    quality = payload.get('quality') or {}
    video_leakage = quality.get('video_leakage') or {}
    group_leakage = quality.get('group_leakage') or {}
    leakage_count = sum(
        int(video_leakage.get(key) or 0) + int(group_leakage.get(key) or 0)
        for key in ('train_val_shared', 'train_test_shared', 'val_test_shared')
    )
    duplicate_track_count = int(quality.get('duplicate_track_count') or 0)
    return {
        'provided': True,
        'duplicate_track_count': duplicate_track_count,
        'group_or_video_leakage_count': leakage_count,
        'failed': bool(duplicate_track_count or leakage_count),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--db',
        default='app/data/db/birdlense.db',
        help='SQLite database path with activity_log',
    )
    parser.add_argument('--dataset-info', help='Optional dataset_info.json for export quality metrics')
    args = parser.parse_args()

    latest_live, latest_regen = _load_latest_traces(args.db)
    live_tracks = list(_iter_persisted_tracks(latest_live))
    yolo_tracks = [
        track for track in live_tracks if str(track.get('primary_provider') or '') == 'yolo'
    ]
    accepted_species = [
        track for track in yolo_tracks if str(track.get('decision_kind') or '') == 'accepted_species'
    ]
    fallback_tracks = [track for track in live_tracks if bool(track.get('fallback_used'))]
    unknown_tracks = [
        track for track in live_tracks if str(track.get('species_name') or '').strip().lower() == 'unknown'
    ]
    comparable = sorted(set(latest_live) & set(latest_regen))
    drifted = [
        video_id
        for video_id in comparable
        if _species_signature(latest_live[video_id]) != _species_signature(latest_regen[video_id])
    ]
    body = {
        'latest_live_video_count': len(latest_live),
        'latest_regen_video_count': len(latest_regen),
        'live_persisted_track_count': len(live_tracks),
        'yolo_species_accept_rate': (
            round(len(accepted_species) / len(yolo_tracks), 4) if yolo_tracks else None
        ),
        'fallback_only_rate': (
            round(len(fallback_tracks) / len(live_tracks), 4) if live_tracks else None
        ),
        'unknown_rate': (
            round(len(unknown_tracks) / len(live_tracks), 4) if live_tracks else None
        ),
        'decision_kind_counts': dict(
            sorted(Counter(str(track.get('decision_kind') or 'unknown') for track in live_tracks).items()),
        ),
        'regen_drift_rate': (
            round(len(drifted) / len(comparable), 4) if comparable else None
        ),
        'regen_drift_videos': drifted,
        'dataset_export_quality': _dataset_export_failures(args.dataset_info),
    }
    print(json.dumps(body, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
