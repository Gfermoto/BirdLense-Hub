#!/usr/bin/env python3
"""A/B evaluation for fusion/arbitration profiles on recorded videos."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_ROOT = os.path.join(ROOT, 'app')
PROCESSOR_SRC = os.path.join(APP_ROOT, 'processor', 'src')
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)
if PROCESSOR_SRC not in sys.path:
    sys.path.insert(0, PROCESSOR_SRC)

from app_config.app_config import app_config
from detection_fusion import build_fused_video_detections
from runtime_contract import apply_runtime_contract_rows
from track_regenerator import build_detection_pipeline, process_video_for_tracks


class ConfigView:
    def __init__(self, base):
        self._base = base

    def get(self, key, default=None):
        return self._base.get(key, default)


def _load_video_rows(db_path: str, start_utc: str, end_utc: str, limit: int) -> list[dict]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        '''
        SELECT id, video_path, created_at
        FROM video
        WHERE created_at >= ? AND created_at < ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (start_utc, end_utc, limit),
    ).fetchall()
    out = [dict(r) for r in rows]
    con.close()
    return out


def _frigate_events_for_video(db_path: str, video_id: int, start_time, end_time) -> list[dict]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        '''
        SELECT
          COALESCE(s.name, 'Bird') AS species_name,
          vs.confidence AS confidence
        FROM video_species vs
        LEFT JOIN species s ON s.id = vs.species_id
        WHERE vs.video_id = ?
          AND COALESCE(vs.detection_provider, '') IN ('frigate', 'arbitration')
        ORDER BY vs.confidence DESC
        ''',
        (video_id,),
    ).fetchall()
    con.close()

    # Synthetic Frigate event feed reconstructed from persisted rows.
    # Needed for deterministic A/B where historical MQTT stream is unavailable.
    ts = end_time.isoformat().replace('+00:00', 'Z')
    events = []
    for r in rows:
        conf = float(r['confidence'] or 0.0)
        if conf <= 0.0:
            continue
        events.append(
            {
                'source': 'frigate',
                'species': str(r['species_name'] or 'Bird'),
                'confidence': conf,
                'timestamp': ts,
            },
        )
    return events


def _profile(base: dict, name: str) -> dict:
    cfg = copy.deepcopy(base)
    if name == 'A':
        cfg['detection.frigate_standalone_when_no_accepted_species'] = True
        cfg['detection.frigate_standalone_min_score'] = 0.48
        cfg['detection.use_learned_fusion'] = True
    elif name == 'B':
        cfg['detection.frigate_standalone_when_no_accepted_species'] = False
        cfg['detection.frigate_standalone_min_score'] = 0.52
        cfg['detection.use_learned_fusion'] = False
    else:
        raise ValueError(f'unknown profile: {name}')
    return cfg


def _collect_metrics(rows: list[dict]) -> dict:
    providers = Counter()
    kinds = Counter()
    reasons = Counter()
    for r in rows:
        providers[str(r.get('primary_provider') or 'unknown')] += 1
        kinds[str(r.get('decision_kind') or 'none')] += 1
        reasons[str(r.get('decision_reason') or 'none')] += 1
    total = len(rows)
    return {
        'total_rows': total,
        'primary_provider_counts': dict(sorted(providers.items())),
        'primary_provider_ratio': {
            k: round(v / max(1, total), 3) for k, v in sorted(providers.items())
        },
        'decision_kind_counts': dict(sorted(kinds.items())),
        'decision_reason_top': reasons.most_common(10),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', required=True, help='UTC start, ex: 2026-04-29 00:00:00')
    parser.add_argument('--end', required=True, help='UTC end, ex: 2026-04-30 00:00:00')
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--frame-step', type=int, default=3)
    parser.add_argument('--lores', type=int, default=640)
    parser.add_argument('--max-runtime-sec', type=int, default=180)
    args = parser.parse_args()

    db_path = '/app/data/db/birdlense.db'
    videos = _load_video_rows(db_path, args.start, args.end, args.limit)
    if not videos:
        print(json.dumps({'error': 'no_videos_in_window'}, ensure_ascii=False))
        return 1

    base_cfg = {}
    keys = [
        'detection.merge_window_seconds',
        'detection.dedup_window_seconds',
        'detection.one_per_species',
        'detection.source_priority',
        'detection.cross_source_confidence_bonus',
        'detection.min_confidence_to_store',
        'detection.frigate_standalone_when_no_yolo',
        'detection.frigate_standalone_when_no_accepted_species',
        'detection.frigate_standalone_min_score',
        'detection.frigate_standalone_missing_score_fallback',
        'detection.use_learned_fusion',
        'detection.fusion_alpha',
        'detection.fusion_model_path',
        'processor.birdnet_mqtt_half_life_hours',
        'processor.multi_camera_groups',
        'processor.multi_camera_confidence_boost',
    ]
    for k in keys:
        base_cfg[k] = app_config.get(k)

    profile_rows = {'A': [], 'B': []}
    video_results = []
    for v in videos:
        video_path_raw = str(v['video_path'] or '').strip()
        video_path = video_path_raw if video_path_raw.startswith('/') else f'/app/{video_path_raw.lstrip("/")}'
        if not os.path.isfile(video_path):
            continue

        start_dt = datetime.now(timezone.utc)
        end_dt = start_dt

        # Raw visual tracks from YOLO+classifier stack.
        fp, dm = build_detection_pipeline(app_config, for_track_regen=True)
        try:
            tracks = process_video_for_tracks(
                video_path,
                lores_size=(args.lores, args.lores),
                frame_processor=fp,
                decision_maker=dm,
                frame_step=args.frame_step,
                max_runtime_sec=args.max_runtime_sec,
            )
        except TimeoutError:
            video_results.append(
                {
                    'video_id': int(v['id']),
                    'created_at': v['created_at'],
                    'video_path': video_path_raw,
                    'error': 'track_regeneration_timeout',
                },
            )
            continue
        frigate_events = _frigate_events_for_video(db_path, int(v['id']), start_dt, end_dt)

        per_video = {
            'video_id': int(v['id']),
            'created_at': v['created_at'],
            'video_path': video_path_raw,
            'raw_tracks': len(tracks),
            'frigate_events': len(frigate_events),
            'profiles': {},
        }
        for name in ('A', 'B'):
            cfg = ConfigView(_profile(base_cfg, name))
            fused = build_fused_video_detections(
                tracks,
                frigate_events,
                start_time=start_dt,
                end_time=end_dt,
                app_config=cfg,
            )
            contracted = apply_runtime_contract_rows(fused)
            profile_rows[name].extend(contracted)
            per_video['profiles'][name] = {
                'fused_rows': len(contracted),
                'providers': dict(
                    sorted(Counter(str(r.get('primary_provider') or 'unknown') for r in contracted).items()),
                ),
            }
        video_results.append(per_video)

    out = {
        'report': 'fusion_ab_eval@v1',
        'captured_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'window': {'start': args.start, 'end': args.end, 'limit': args.limit},
        'profiles': {
            'A': _collect_metrics(profile_rows['A']),
            'B': _collect_metrics(profile_rows['B']),
        },
        'videos': video_results,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
