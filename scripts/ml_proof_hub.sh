#!/usr/bin/env bash
# Reproducible ML proof gate on deployed hub:
# - OpenVINO GPU visibility + steady latency smoke
# - detector_continuity_report@v1 from live SQLite
# - track_continuity_eval@v1 from continuity artifact
# Outputs ml_proof_hub_report@v1 JSON and exits non-zero on gate fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "${SCRIPT_DIR}/deploy.local.sh" ]; then
  # shellcheck disable=SC1091
  . "${SCRIPT_DIR}/deploy.local.sh"
fi

HOST="${DEPLOY_HOST:-birdlense}"
PORT="${DEPLOY_SSH_PORT:-22}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
REMOTE_TMP="${REMOTE_TMP:-/tmp/bl_metrics}"
DB_PATH="${DB_PATH:-${REMOTE_DIR}/app/data/db/birdlense.db}"
DAYS="${DAYS:-14}"
MAX_GPU_STEADY_MS="${MAX_GPU_STEADY_MS:-120}"
MIN_TRACK_EMIT_SUCCESS_RATE="${MIN_TRACK_EMIT_SUCCESS_RATE:-0.995}"
MAX_EMPTY_TRACK_RATE="${MAX_EMPTY_TRACK_RATE:-0.01}"

VIDEO_1="${VIDEO_1:-/app/data/recordings/2026/04/26/011445/video.mp4}"
VIDEO_2="${VIDEO_2:-/app/data/recordings/2026/04/26/011642/video.mp4}"
VIDEO_3="${VIDEO_3:-/app/data/recordings/2026/04/26/011854/video.mp4}"

SSH_OPTS=(-p "${PORT}" -o ServerAliveInterval=30 -o ServerAliveCountMax=20)

echo "ml-proof-hub: host=${HOST} db=${DB_PATH} tmp=${REMOTE_TMP}"

ssh "${SSH_OPTS[@]}" "${HOST}" "mkdir -p '${REMOTE_TMP}'"

ssh "${SSH_OPTS[@]}" "${HOST}" \
  "python3 '${REMOTE_DIR}/scripts/ml_detector_continuity_report.py' \
    --db '${DB_PATH}' \
    --days '${DAYS}' \
    --out '${REMOTE_TMP}/detector_continuity_report.v1.json' >/dev/null"

ssh "${SSH_OPTS[@]}" "${HOST}" \
  "python3 '${REMOTE_DIR}/scripts/ml_track_continuity_eval.py' \
    --continuity-report '${REMOTE_TMP}/detector_continuity_report.v1.json' \
    --max-empty-track-rate '${MAX_EMPTY_TRACK_RATE}' \
    --min-track-emit-success-rate '${MIN_TRACK_EMIT_SUCCESS_RATE}' \
    --out '${REMOTE_TMP}/track_continuity_eval.v1.json' >/dev/null"

ssh "${SSH_OPTS[@]}" "${HOST}" \
  "docker exec -i birdlense python3 - <<'PY'
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
from openvino import Core
from ultralytics import YOLO

video_candidates = [
    '${VIDEO_1}',
    '${VIDEO_2}',
    '${VIDEO_3}',
]
video_path = None
frame = None
for path in video_candidates:
    cap = cv2.VideoCapture(path)
    ok, fr = cap.read()
    cap.release()
    if ok and fr is not None:
        video_path = path
        frame = fr
        break

ie = Core()
devices = list(ie.available_devices)
gpu_present = any(str(d).upper().startswith('GPU') for d in devices)

steady = []
model_error = None
if frame is not None and gpu_present:
    try:
        model = YOLO('/app/processor/models/detection/weights/best_openvino_model')
        model.predict(frame, device='intel:gpu', conf=0.15, imgsz=640, verbose=False)
        for _ in range(5):
            t0 = time.perf_counter()
            model.predict(frame, device='intel:gpu', conf=0.15, imgsz=640, verbose=False)
            steady.append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:  # pragma: no cover - runtime dependent
        model_error = str(exc)

def p95(values):
    if not values:
        return None
    s = sorted(values)
    idx = max(0, min(len(s) - 1, math.ceil(0.95 * len(s)) - 1))
    return float(s[idx])

out = {
    'schema': 'openvino_gpu_smoke@v1',
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'video_path': video_path,
    'openvino_devices': devices,
    'gpu_present': gpu_present,
    'steady_latency_ms': [round(float(v), 3) for v in steady],
    'steady_mean_ms': round(sum(steady) / len(steady), 3) if steady else None,
    'steady_p95_ms': round(p95(steady), 3) if steady else None,
    'model_error': model_error,
}
out_path = Path('${REMOTE_TMP}/openvino_gpu_smoke.v1.json')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding='utf-8',
)
print(json.dumps(out, ensure_ascii=False, indent=2))
PY"

ssh "${SSH_OPTS[@]}" "${HOST}" \
  "docker cp 'birdlense:${REMOTE_TMP}/openvino_gpu_smoke.v1.json' '${REMOTE_TMP}/openvino_gpu_smoke.v1.json' >/dev/null"

ssh "${SSH_OPTS[@]}" "${HOST}" \
  "python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

base = Path('${REMOTE_TMP}')
continuity = json.loads((base / 'detector_continuity_report.v1.json').read_text(encoding='utf-8'))
track_eval = json.loads((base / 'track_continuity_eval.v1.json').read_text(encoding='utf-8'))
gpu_smoke = json.loads((base / 'openvino_gpu_smoke.v1.json').read_text(encoding='utf-8'))

gates = {
    'continuity_ok': bool(continuity.get('ok')),
    'track_eval_ok': bool(track_eval.get('ok')),
    'openvino_gpu_visible': bool(gpu_smoke.get('gpu_present')),
    'openvino_gpu_latency_ok': (
        gpu_smoke.get('steady_mean_ms') is not None
        and float(gpu_smoke.get('steady_mean_ms')) <= float('${MAX_GPU_STEADY_MS}')
    ),
    'openvino_model_error_absent': not bool(gpu_smoke.get('model_error')),
}
out = {
    'schema': 'ml_proof_hub_report@v1',
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'inputs': {
        'db_path': '${DB_PATH}',
        'days': int('${DAYS}'),
        'max_gpu_steady_ms': float('${MAX_GPU_STEADY_MS}'),
        'min_track_emit_success_rate': float('${MIN_TRACK_EMIT_SUCCESS_RATE}'),
        'max_empty_track_rate': float('${MAX_EMPTY_TRACK_RATE}'),
    },
    'metrics': {
        'track_emit_success_rate': track_eval.get('metrics', {}).get('track_emit_success_rate'),
        'empty_track_with_detection_rate': track_eval.get('metrics', {}).get('empty_track_with_detection_rate'),
        'openvino_devices': gpu_smoke.get('openvino_devices', []),
        'openvino_gpu_steady_mean_ms': gpu_smoke.get('steady_mean_ms'),
        'openvino_gpu_steady_p95_ms': gpu_smoke.get('steady_p95_ms'),
        'openvino_video_path': gpu_smoke.get('video_path'),
    },
    'gates': gates,
    'ok': all(bool(v) for v in gates.values()),
}
report_path = base / 'ml_proof_hub_report.v1.json'
report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
raise SystemExit(0 if out['ok'] else 3)
PY"
