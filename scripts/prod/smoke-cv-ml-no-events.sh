#!/usr/bin/env bash
set -euo pipefail

# Production smoke for CV/ML pipeline without waiting for live feeder events.
# Uses existing recordings from DB and dry-run checks only (no config mutation).

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_LOCAL="${ROOT_DIR}/scripts/deploy.local.sh"

if [[ ! -f "${DEPLOY_LOCAL}" ]]; then
  echo "ERROR: missing ${DEPLOY_LOCAL}" >&2
  exit 2
fi

# shellcheck disable=SC1090
source "${DEPLOY_LOCAL}"

: "${DEPLOY_HOST:?DEPLOY_HOST is required}"
: "${DEPLOY_REMOTE_DIR:?DEPLOY_REMOTE_DIR is required}"

if [[ -n "${DEPLOY_SSH_PORT:-}" ]]; then
  SSH_ARGS=(-p "${DEPLOY_SSH_PORT}")
else
  SSH_ARGS=()
fi

echo "=== Target ==="
echo "DEPLOY_HOST=${DEPLOY_HOST}"
echo "DEPLOY_SSH_PORT=${DEPLOY_SSH_PORT:-22}"
echo "DEPLOY_URL=${DEPLOY_URL:-}"
echo "DEPLOY_REMOTE_DIR=${DEPLOY_REMOTE_DIR}"
echo

ssh "${SSH_ARGS[@]}" "${DEPLOY_HOST}" "cd ${DEPLOY_REMOTE_DIR}/app && docker exec -i birdlense python3 - <<'PY'
import json
import os
import sqlite3
import sys
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2

sys.path.insert(0, '/app')
sys.path.insert(0, '/app/web')
sys.path.insert(0, '/app/processor/src')

from app_config.app_config import app_config
from app_config.trigger_config import get_active_trigger_names, get_effective_trigger_config
from app import app as flask_app
from detection_stack import build_detection_stack
from models import db
try:
    from services.feedback_loop_service import build_feedback_loop_status
except Exception:
    build_feedback_loop_status = None
from services.ml_ops_service import (
    build_reid_summary,
    build_video_action_events_payload,
    build_video_reid_match_payload,
)
try:
    sys.path.insert(0, '/app/scripts')
    from verify_action_labeling_gates import verify_action_gates
    from verify_reid_production_gates import verify_reid_gates
except Exception:
    verify_action_gates = None
    verify_reid_gates = None

db_path = '/app/data/db/birdlense.db'
if not os.path.isfile(db_path):
    raise SystemExit(f'Missing DB: {db_path}')

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print('=== Runtime config snapshot ===')
cfg = OrderedDict()
cfg['inference_backend'] = app_config.get('processor.inference_backend')
cfg['classifier_inference_backend'] = app_config.get('processor.classifier_inference_backend')
cfg['binary_imgsz'] = app_config.get('processor.binary_imgsz')
cfg['inference_lores_px'] = app_config.get('processor.inference_lores_px')
cfg['night_binary_imgsz'] = app_config.get('processor.adaptive_profiles.night.overrides.binary_imgsz')
cfg['frigate_min_trigger_score'] = app_config.get('motion.frigate_min_trigger_score')
cfg['active_triggers'] = get_active_trigger_names(app_config)
print(json.dumps(cfg, ensure_ascii=False, indent=2))

print()
print('=== Effective trigger config (opencv+frigate) ===')
tcfg = get_effective_trigger_config(app_config)
print(json.dumps({
    'opencv': tcfg.get('opencv', {}),
    'frigate': tcfg.get('frigate', {}),
}, ensure_ascii=False, indent=2))

print()
print('=== DB throughput check ===')
now = datetime.now(timezone.utc)
for hours in (1, 6, 24):
    cutoff = (now - timedelta(hours=hours)).isoformat()
    v = cur.execute('SELECT COUNT(1) FROM video WHERE start_time >= ?', (cutoff,)).fetchone()[0]
    s = cur.execute('SELECT COUNT(1) FROM video_species WHERE created_at >= ?', (cutoff,)).fetchone()[0]
    print(f'window_{hours}h: videos={v} video_species={s}')

print()
print('=== Synthetic Frigate score gate (dry-run) ===')
min_score = float(app_config.get('motion.frigate_min_trigger_score') or 0.0)
for score in (0.45, 0.50, 0.55, 0.66, 0.72):
    decision = 'accept' if score >= min_score else 'reject'
    print(f'score={score:.2f} min={min_score:.2f} -> {decision}')

rows = cur.execute(
    'SELECT id, video_path FROM video WHERE video_path IS NOT NULL AND TRIM(video_path) != \"\" '
    'ORDER BY start_time DESC LIMIT 3'
).fetchall()
if not rows:
    raise SystemExit('No videos in DB for smoke run')

print()
print('=== Detector smoke on latest DB videos ===')
frame_processor, _decision_maker, _diag = build_detection_stack(app_config)
tracker = str(app_config.get('processor.tracker') or 'bytetrack.yaml')
min_conf = float(app_config.get('processor.min_confidence_binary') or 0.0)

def _resolve_video_path(raw: str) -> str:
    p = str(raw or '').strip()
    if not p:
        return ''
    if os.path.isabs(p):
        return p
    cand = os.path.join('/app', p.lstrip('/'))
    if os.path.isfile(cand):
        return cand
    cand2 = os.path.join('/app/data', p.replace('data/', '', 1).lstrip('/'))
    return cand2

smoke = []
for vid, raw_path in rows:
    full_path = _resolve_video_path(raw_path)
    item = {'video_id': int(vid), 'video_path': raw_path, 'resolved_path': full_path}
    if not os.path.isfile(full_path):
        item['status'] = 'missing_file'
        smoke.append(item)
        continue
    cap = cv2.VideoCapture(full_path)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        item['status'] = 'decode_failed'
        smoke.append(item)
        continue
    try:
        det = frame_processor.strategy.detect(
            frame,
            tracker_config=tracker,
            min_confidence=min_conf,
        )
        item['status'] = 'ok'
        item['detections'] = len(det or [])
    except Exception as exc:
        item['status'] = f'detect_error:{type(exc).__name__}'
        item['error'] = str(exc)
    smoke.append(item)

print(json.dumps(smoke, ensure_ascii=False, indent=2))
print()

latest_video_id = int(rows[0][0])
print('=== Product-slice API payload smoke ===')
with flask_app.app_context():
    action_payload, action_code = build_video_action_events_payload(db.session, latest_video_id)
    reid_payload, reid_code = build_video_reid_match_payload(db.session, latest_video_id)
    reid_summary_payload, reid_summary_code = build_reid_summary(db.session)
    if build_feedback_loop_status is not None:
        feedback_status = build_feedback_loop_status(db.session, data_dir='/app/data')
    else:
        feedback_status = {
            'schema': 'feedback_loop_status@v1',
            'status': 'service_unavailable_in_runtime',
            'total_events': 0,
        }
print(json.dumps({
    'video_id': latest_video_id,
    'video_action_events_http': int(action_code),
    'video_action_events_schema': action_payload.get('schema'),
    'video_action_events_available': bool(action_payload.get('available')),
    'video_reid_match_http': int(reid_code),
    'video_reid_match_schema': reid_payload.get('schema'),
    'video_reid_match_available': bool(reid_payload.get('available')),
    'reid_summary_http': int(reid_summary_code),
    'reid_summary_schema': reid_summary_payload.get('schema'),
    'reid_summary_contract_status': ((reid_summary_payload.get('contract') or {}).get('status')),
    'feedback_loop_schema': feedback_status.get('schema'),
    'feedback_total_events': int(feedback_status.get('total_events', 0)),
}, ensure_ascii=False, indent=2))
print()

print('=== Execution gates smoke (#389/#390/#392) ===')
if verify_reid_gates is not None:
    reid_ok, reid_gate = verify_reid_gates(
        reid_summary=reid_summary_payload,
        reid_match=reid_payload,
        min_embeddings=0,
        max_missing_contract_rows=0,
        require_contract_ok=True,
        max_stale_hours=None,
        min_suggestion_count=0,
    )
else:
    contract_status = ((reid_summary_payload.get('contract') or {}).get('status'))
    reid_ok = (
        reid_summary_payload.get('schema') == 'reid_summary@v2'
        and bool(reid_summary_payload.get('available'))
        and contract_status == 'ok'
    )
    reid_gate = {
        'schema': 'reid_production_gates@v1',
        'ok': bool(reid_ok),
        'fallback': True,
        'checks': {
            'summary_schema': reid_summary_payload.get('schema'),
            'summary_available': bool(reid_summary_payload.get('available')),
            'contract_status': contract_status,
        },
        'errors': [] if reid_ok else ['reid_fallback_gate_failed'],
    }

if verify_action_gates is not None:
    action_ok, action_gate = verify_action_gates(
        action_events=action_payload,
        dataset_rows=None,
        min_events=1,
        min_dataset_rows=0,
        min_segment_ms=300,
        allow_extended_labels=False,
    )
else:
    events = action_payload.get('events') if isinstance(action_payload.get('events'), list) else []
    action_ok = (
        action_payload.get('schema') == 'video_action_events@v1'
        and bool(action_payload.get('available'))
        and len(events) >= 1
    )
    action_gate = {
        'schema': 'action_labeling_gates@v1',
        'ok': bool(action_ok),
        'fallback': True,
        'checks': {
            'action_events_schema': action_payload.get('schema'),
            'action_events_available': bool(action_payload.get('available')),
            'action_events_count': len(events),
        },
        'errors': [] if action_ok else ['action_fallback_gate_failed'],
    }
print(json.dumps({
    'reid_gate_ok': bool(reid_ok),
    'reid_gate': reid_gate,
    'action_gate_ok': bool(action_ok),
    'action_gate': action_gate,
}, ensure_ascii=False, indent=2))
print()
if not reid_ok:
    raise SystemExit('reid production gate failed')
if not action_ok:
    raise SystemExit('action labeling gate failed')

print('Smoke no-events completed.')
PY"
