#!/usr/bin/env bash
set -euo pipefail

# Emits synthetic Frigate MQTT event from inside running birdlense container.
# Default mode is dry-run (no publish). Pass --publish to actually send MQTT message.
#
# Usage:
#   scripts/prod/emit-synthetic-frigate-event.sh --score 0.66 --camera BirdBox --label bird --publish

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_LOCAL="${ROOT_DIR}/scripts/deploy.local.sh"

if [[ ! -f "${DEPLOY_LOCAL}" ]]; then
  echo "ERROR: missing ${DEPLOY_LOCAL}" >&2
  exit 2
fi

SCORE="0.66"
CAMERA="BirdBox"
LABEL="bird"
PUBLISH="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --score) SCORE="${2:-}"; shift 2 ;;
    --camera) CAMERA="${2:-}"; shift 2 ;;
    --label) LABEL="${2:-}"; shift 2 ;;
    --publish) PUBLISH="1"; shift ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

# shellcheck disable=SC1090
source "${DEPLOY_LOCAL}"

: "${DEPLOY_HOST:?DEPLOY_HOST is required}"
: "${DEPLOY_REMOTE_DIR:?DEPLOY_REMOTE_DIR is required}"

if [[ -n "${DEPLOY_SSH_PORT:-}" ]]; then
  SSH_ARGS=(-p "${DEPLOY_SSH_PORT}")
else
  SSH_ARGS=()
fi

ssh "${SSH_ARGS[@]}" "${DEPLOY_HOST}" "cd ${DEPLOY_REMOTE_DIR}/app && docker exec -i -e SCORE='${SCORE}' -e CAMERA='${CAMERA}' -e LABEL='${LABEL}' -e PUBLISH='${PUBLISH}' birdlense python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

sys.path.insert(0, '/app')
from app_config.app_config import app_config

score = float(os.environ.get('SCORE', '0.66'))
camera = os.environ.get('CAMERA', 'BirdBox').strip() or 'BirdBox'
label = os.environ.get('LABEL', 'bird').strip() or 'bird'
publish = os.environ.get('PUBLISH', '0') == '1'

topic = str(app_config.get('mqtt.frigate_topic') or 'frigate/events').strip() or 'frigate/events'
broker = str(app_config.get('mqtt.broker') or '').strip()
port = int(app_config.get('mqtt.port', 1883) or 1883)
username = str(app_config.get('mqtt.username') or '').strip()
password = str(app_config.get('mqtt.password') or '').strip()
min_score = float(app_config.get('motion.frigate_min_trigger_score') or 0.0)

event = {
    'type': 'new',
    'before': {},
    'after': {
        'camera': camera,
        'label': label,
        'score': score,
        'top_score': score,
        'box': [0.15, 0.12, 0.65, 0.74],
        'frame_time': datetime.now(timezone.utc).timestamp(),
    },
}

print('synthetic_event=', json.dumps(event, ensure_ascii=False))
print(f'topic={topic} broker={broker or \"<empty>\"}:{port}')
print(f'frigate_min_trigger_score={min_score:.3f} decision={(\"accept\" if score >= min_score else \"reject\")}')

if not publish:
    print('mode=dry-run (no MQTT publish)')
    raise SystemExit(0)

if not broker:
    raise SystemExit('mqtt.broker is empty; cannot publish synthetic event')

client = mqtt.Client()
if username:
    client.username_pw_set(username, password or None)
client.connect(broker, port=port, keepalive=15)
info = client.publish(topic, payload=json.dumps(event), qos=0, retain=False)
info.wait_for_publish(timeout=5)
client.disconnect()
print(f'published=true mid={info.mid} rc={info.rc}')
PY"
