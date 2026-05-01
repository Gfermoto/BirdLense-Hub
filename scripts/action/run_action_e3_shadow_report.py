#!/usr/bin/env python3
# flake8: noqa
"""Run E3 shadow report for action/Re-ID runtime outcomes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _bootstrap_imports(root: Path) -> None:
    app_dir = root / 'app'
    web_dir = root / 'app' / 'web'
    proc_dir = root / 'app' / 'processor' / 'src'
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    if str(web_dir) not in sys.path:
        sys.path.insert(0, str(web_dir))
    if str(proc_dir) not in sys.path:
        sys.path.insert(0, str(proc_dir))
    os.environ.setdefault('FLASK_CREATE_APP_ON_IMPORT', '0')
    os.environ['BIRDLENSE_ENV'] = 'development'
    os.environ['FLASK_ENV'] = 'development'


def _parse_activity_data(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window-hours', type=int, default=24)
    parser.add_argument('--video-limit', type=int, default=300)
    parser.add_argument('--output-json', required=True)
    parser.add_argument('--min-action-available-ratio', type=float, default=0.95)
    parser.add_argument('--min-reid-available-ratio', type=float, default=0.90)
    parser.add_argument('--max-reid-reject-proxy-ratio', type=float, default=0.50)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    _bootstrap_imports(root)

    from app import create_app
    from models import db, Video, VideoSpecies, DetectionFeedbackEvent, ActivityLog
    from services.ml_ops_service import (
        build_reid_summary,
        build_video_action_events_payload,
        build_video_reid_match_payload,
    )
    from util import ensure_utc

    out_path = Path(args.output_json).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    app = create_app()
    cutoff = _now_utc() - timedelta(hours=max(1, int(args.window_hours)))

    with app.app_context():
        videos = (
            db.session.query(Video)
            .filter(Video.start_time >= cutoff.isoformat())
            .order_by(Video.start_time.desc(), Video.id.desc())
            .limit(max(1, int(args.video_limit)))
            .all()
        )

        action_available = 0
        action_schema_ok = 0
        action_event_total = 0
        action_label_counts: Counter[str] = Counter()
        action_errors: list[dict[str, Any]] = []

        reid_available = 0
        reid_schema_ok = 0
        reid_match_total = 0
        reid_suggest_total = 0
        reid_with_candidate_nickname = 0
        reid_outcomes = Counter()
        reid_errors: list[dict[str, Any]] = []

        video_ids = [int(v.id) for v in videos]
        nickname_rows = (
            db.session.query(VideoSpecies.id, VideoSpecies.individual_nickname)
            .filter(VideoSpecies.video_id.in_(video_ids))
            .all()
            if video_ids
            else []
        )
        nickname_by_id = {
            int(vsid): (str(nick).strip() if nick is not None else None)
            for vsid, nick in nickname_rows
        }

        for v in videos:
            action_payload, action_code = build_video_action_events_payload(db.session, int(v.id))
            if int(action_code) != 200:
                action_errors.append({'video_id': int(v.id), 'http': int(action_code)})
                continue
            if action_payload.get('schema') == 'video_action_events@v1':
                action_schema_ok += 1
            if bool(action_payload.get('available')):
                action_available += 1
            events = action_payload.get('events') if isinstance(action_payload.get('events'), list) else []
            action_event_total += len(events)
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                action_label_counts[str(ev.get('label') or '')] += 1

            reid_payload, reid_code = build_video_reid_match_payload(db.session, int(v.id))
            if int(reid_code) != 200:
                reid_errors.append({'video_id': int(v.id), 'http': int(reid_code)})
                continue
            if reid_payload.get('schema') == 'video_reid_match@v2':
                reid_schema_ok += 1
            if bool(reid_payload.get('available')):
                reid_available += 1
            matches = reid_payload.get('matches') if isinstance(reid_payload.get('matches'), list) else []
            reid_match_total += len(matches)
            for m in matches:
                if not isinstance(m, dict):
                    continue
                if str(m.get('decision') or '') == 'suggest_same_individual':
                    reid_suggest_total += 1
                candidate_nickname = str(m.get('candidate_nickname') or '').strip()
                if candidate_nickname:
                    reid_with_candidate_nickname += 1
                det_id = m.get('video_species_id')
                current_nickname = nickname_by_id.get(int(det_id)) if det_id is not None else None
                if not candidate_nickname:
                    reid_outcomes['pending_no_candidate_nickname'] += 1
                    continue
                if not current_nickname:
                    reid_outcomes['pending_no_operator_nickname'] += 1
                elif current_nickname.casefold() == candidate_nickname.casefold():
                    reid_outcomes['accepted_proxy'] += 1
                else:
                    reid_outcomes['rejected_proxy'] += 1

        reid_summary_payload, reid_summary_code = build_reid_summary(db.session)

        feedback_rows = (
            db.session.query(DetectionFeedbackEvent.action)
            .filter(DetectionFeedbackEvent.created_at >= cutoff.isoformat())
            .all()
        )
        feedback_counts = Counter(str(r[0] or '') for r in feedback_rows)

        activity_rows = (
            db.session.query(ActivityLog.created_at, ActivityLog.data)
            .filter(ActivityLog.type == 'species_correction')
            .filter(ActivityLog.created_at >= cutoff.isoformat())
            .all()
        )
        correction_action_counts = Counter()
        for _created_at, data in activity_rows:
            payload = _parse_activity_data(data)
            correction_action_counts[str(payload.get('action') or 'unknown')] += 1

    videos_n = len(videos)
    action_available_ratio = (action_available / videos_n) if videos_n else 0.0
    reid_available_ratio = (reid_available / videos_n) if videos_n else 0.0
    reid_decided = int(reid_outcomes.get('accepted_proxy', 0) + reid_outcomes.get('rejected_proxy', 0))
    reid_reject_proxy_ratio = (
        float(reid_outcomes.get('rejected_proxy', 0)) / float(reid_decided)
        if reid_decided > 0
        else 0.0
    )

    if videos_n > 0:
        gates: dict[str, Any] = {
            'action_available_ratio_ok': action_available_ratio >= float(args.min_action_available_ratio),
            'reid_available_ratio_ok': reid_available_ratio >= float(args.min_reid_available_ratio),
            'reid_reject_proxy_ratio_ok': reid_reject_proxy_ratio <= float(args.max_reid_reject_proxy_ratio),
        }
    else:
        gates = {
            'action_available_ratio_ok': None,
            'reid_available_ratio_ok': None,
            'reid_reject_proxy_ratio_ok': None,
        }

    report = {
        'schema': 'action_e3_shadow_report@v1',
        'generated_at_utc': _now_utc().isoformat(),
        'window_hours': int(args.window_hours),
        'video_limit': int(args.video_limit),
        'videos_evaluated': videos_n,
        'action': {
            'schema_ok_count': action_schema_ok,
            'available_count': action_available,
            'available_ratio': round(action_available_ratio, 6),
            'events_total': action_event_total,
            'label_counts': dict(action_label_counts),
            'errors': action_errors,
        },
        'reid': {
            'schema_ok_count': reid_schema_ok,
            'available_count': reid_available,
            'available_ratio': round(reid_available_ratio, 6),
            'matches_total': reid_match_total,
            'suggest_same_total': reid_suggest_total,
            'with_candidate_nickname': reid_with_candidate_nickname,
            'outcomes_proxy': dict(reid_outcomes),
            'reject_proxy_ratio': round(reid_reject_proxy_ratio, 6),
            'errors': reid_errors,
            'summary_http': int(reid_summary_code),
            'summary_schema': reid_summary_payload.get('schema'),
            'summary_contract_status': ((reid_summary_payload.get('contract') or {}).get('status')),
        },
        'operator_outcomes': {
            'feedback_event_counts': dict(feedback_counts),
            'species_correction_action_counts': dict(correction_action_counts),
        },
        'gates': {
            'thresholds': {
                'min_action_available_ratio': float(args.min_action_available_ratio),
                'min_reid_available_ratio': float(args.min_reid_available_ratio),
                'max_reid_reject_proxy_ratio': float(args.max_reid_reject_proxy_ratio),
            },
            'checks': gates,
        },
        'data_available': videos_n > 0,
        'ok': (all(bool(v) for v in gates.values()) if videos_n > 0 else True),
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
