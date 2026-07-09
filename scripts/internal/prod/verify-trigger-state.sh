#!/usr/bin/env bash
set -euo pipefail

# Production read-only probe for trigger runtime state.
# Prints:
# - target deploy vars
# - container started timestamp
# - effective trigger config from running container
# - recent trigger-related log lines

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
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

ssh "${SSH_ARGS[@]}" "${DEPLOY_HOST}" "cd ${DEPLOY_REMOTE_DIR}/app && docker inspect -f '{{.State.StartedAt}}' birdlense && docker exec birdlense python3 -c \"import sys; sys.path.insert(0,'/app'); from app_config.app_config import app_config; from app_config.trigger_config import get_effective_trigger_config,get_active_trigger_names; c=get_effective_trigger_config(app_config); print('active=',get_active_trigger_names(app_config)); print('opencv=',c['opencv']); print('frigate=',{'enabled':c['frigate']['enabled'],'topic':c['frigate']['topic'],'min_trigger_score':c['frigate']['min_trigger_score'],'trigger_on_tracked_object':c['frigate']['trigger_on_tracked_object']}); print('motion.source=',app_config.get('motion.source')); print('motion.opencv_diff_threshold=',app_config.get('motion.opencv_diff_threshold')); print('motion.opencv_min_contour_area=',app_config.get('motion.opencv_min_contour_area')); print('night.max_brightness=',app_config.get('processor.adaptive_profiles.night.max_brightness')); print('night.max_contrast=',app_config.get('processor.adaptive_profiles.night.max_contrast')); print('night.overrides=',app_config.get('processor.adaptive_profiles.night.overrides'))\" && docker compose logs --since 20m --tail 300 birdlense 2>&1 | python3 -c \"import sys; [print(l.rstrip()) for l in sys.stdin if ('motion grouped triggers active' in l.lower()) or ('frigate trigger accepted' in l.lower()) or ('frigate trigger rejected' in l.lower()) or ('motion_detectors.or_motion' in l.lower())]\""
