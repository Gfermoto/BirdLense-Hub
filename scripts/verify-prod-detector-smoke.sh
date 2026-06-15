#!/usr/bin/env bash
# Post-deploy detector smoke: merged config guards + optional one-frame YOLO (#YOLO-blind).
# Exit 0 = config OK; 1 = critical config violation. YOLO smoke warn-only unless --strict-yolo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
STRICT_YOLO=0
YOLO_SMOKE=1

usage() {
  echo "usage: $0 [--strict-yolo] [--no-yolo-smoke]" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict-yolo) STRICT_YOLO=1; shift ;;
    --no-yolo-smoke) YOLO_SMOKE=0; shift ;;
    -h | --help) usage ;;
    *) echo "unknown option: $1" >&2; usage ;;
  esac
done

_SSH_PORT_OPT=()
if [[ -n "${DEPLOY_SSH_PORT:-}" && "${DEPLOY_SSH_PORT}" != "22" ]]; then
  _SSH_PORT_OPT=(-p "${DEPLOY_SSH_PORT}")
fi

_run_local() {
  local yolo_flag=()
  if [[ "${YOLO_SMOKE}" -eq 1 ]]; then
    yolo_flag=(--yolo-smoke)
  fi
  python3 "${ROOT}/scripts/verify_merged_detector_config.py" \
    --default-config "${ROOT}/app/app_config/default_config.yaml" \
    --user-config "${ROOT}/app/app_config/user_config.yaml" \
    "${yolo_flag[@]}" --json
}

if [[ -z "${HOST}" || "${HOST}" == "localhost" || "${HOST}" == "127.0.0.1" ]]; then
  echo "verify-prod-detector-smoke: local merged config"
  _run_local
  exit $?
fi

echo "verify-prod-detector-smoke: remote ${HOST} (container merged config)"
YOLO_ARG=""
[[ "${YOLO_SMOKE}" -eq 1 ]] && YOLO_ARG="--yolo-smoke"

json="$(ssh "${_SSH_PORT_OPT[@]}" "${HOST}" bash -s <<ENDSSH
set -euo pipefail
cd '${REMOTE_DIR}'
if docker ps --filter name=^birdlense$ --format '{{.Status}}' | grep -q '^Up '; then
  docker exec birdlense python3 /app/scripts/verify_merged_detector_config.py \
    --default-config /app/app_config/default_config.yaml \
    --user-config /app/app_config/user_config.yaml \
    ${YOLO_ARG} --json
else
  python3 ./scripts/verify_merged_detector_config.py \
    --default-config ./app/app_config/default_config.yaml \
    --user-config ./app/app_config/user_config.yaml \
    ${YOLO_ARG} --json
fi
ENDSSH
)"

echo "${json}" | python3 - <<'PY'
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    print("verify-prod-detector-smoke: empty response", file=sys.stderr)
    raise SystemExit(1)
report = json.loads(raw)
print(
    f"merged_detector_guards: ok={report.get('ok')} "
    f"critical={report.get('critical_count')} warn={report.get('warn_count')}"
)
for item in report.get("issues") or []:
    print(f"  CRITICAL {item.get('key')}: {item.get('reason')}")
for item in report.get("warnings") or []:
    print(f"  WARN {item.get('key')}: {item.get('reason')}")
ys = report.get("yolo_smoke")
if ys:
    print(f"  yolo_smoke: {ys.get('status')} ({ys.get('reason') or ys.get('error', '')})")
if not report.get("ok"):
    raise SystemExit(1)
PY

cfg_ok=$?

if [[ "${YOLO_SMOKE}" -eq 1 ]]; then
  yolo_status="$(echo "${json}" | python3 -c 'import json,sys; r=json.load(sys.stdin); print((r.get("yolo_smoke") or {}).get("status",""))')"
  if [[ "${yolo_status}" == "error" && "${STRICT_YOLO}" -eq 1 ]]; then
    echo "verify-prod-detector-smoke: yolo_smoke error (strict)" >&2
    exit 1
  fi
  if [[ "${yolo_status}" == "warn" ]]; then
    echo "verify-prod-detector-smoke: WARN yolo_smoke zero boxes (non-blocking)" >&2
  fi
fi

echo "verify-prod-detector-smoke: health curl ${DEPLOY_URL:-}"
curl -sf "${DEPLOY_URL:-http://localhost:8085}/api/ui/health" | head -c 200 || {
  echo "verify-prod-detector-smoke: health unreachable (non-blocking for config-only)" >&2
}

exit "${cfg_ok}"
