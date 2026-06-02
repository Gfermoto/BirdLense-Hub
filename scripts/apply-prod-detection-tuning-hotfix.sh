#!/usr/bin/env bash
# Apply detection tuning hotfix on prod user_config (#587). Does NOT touch repo user_config.yaml.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
CFG="${REMOTE_DIR}/app/app_config/user_config.yaml"

if [[ -z "${HOST}" ]]; then
  echo "DEPLOY_HOST not set" >&2
  exit 2
fi

_PORT_OPT=()
if [[ -n "${DEPLOY_SSH_PORT:-}" && "${DEPLOY_SSH_PORT}" != "22" ]]; then
  _PORT_OPT=(-p "${DEPLOY_SSH_PORT}")
fi

echo "apply-prod-detection-tuning: ${HOST}:${CFG}"
ssh "${_PORT_OPT[@]}" "${HOST}" python3 - <<'PY' "${CFG}"
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
text = cfg_path.read_text(encoding="utf-8")
bak = cfg_path.with_name(
    cfg_path.name + ".bak-tuning-hotfix"
)
if not bak.exists():
    bak.write_text(text, encoding="utf-8")

try:
    import yaml
except ImportError:
    raise SystemExit("PyYAML required on remote host")

data = yaml.safe_load(text) or {}
proc = data.setdefault("processor", {})
proc["track_static_reject_min_duration_sec"] = 2.0
proc["track_static_reject_min_duration_sparse_sec"] = 2.5
proc["track_static_reject_min_frames"] = 4
proc["track_static_reject_min_frames_sparse"] = 3
proc["track_static_reject_max_center_dispersion_norm"] = 0.075
proc["track_static_reject_max_relative_center_dispersion"] = 0.16
proc["track_static_reject_max_bbox_iou_first_last_min"] = 0.74

overrides = proc.setdefault("camera_overrides", {})
bird = overrides.setdefault("BirdBox", {})
for key in (
    "min_confidence_binary",
    "min_confidence_binary_bird",
    "min_confidence_to_process",
    "openvino_min_confidence_binary_bird",
):
    bird[key] = 0.12

forest = overrides.setdefault("Forest", {})
forest["track_static_reject_max_center_dispersion_norm"] = 0.10
forest["track_static_reject_max_relative_center_dispersion"] = 0.18
forest["track_static_reject_min_duration_sec"] = 2.5
forest["track_static_reject_min_frames"] = 3
forest["track_static_reject_min_frames_sparse"] = 2

cfg_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
print("OK:", cfg_path)
print("backup:", bak)
PY

ssh "${_PORT_OPT[@]}" "${HOST}" "cd '${REMOTE_DIR}/app' && docker compose restart birdlense"
echo "apply-prod-detection-tuning: restarted birdlense"
