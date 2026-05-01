#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/app"

MODE="full"
for arg in "$@"; do
  case "$arg" in
    --quick) MODE="quick" ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--quick]" >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "${APP_DIR}" ]]; then
  echo "ERROR: missing app dir: ${APP_DIR}" >&2
  exit 2
fi

if [[ -x "${APP_DIR}/.venv/bin/pytest" ]]; then
  PYTEST="${APP_DIR}/.venv/bin/pytest"
else
  PYTEST="pytest"
fi

echo "== CV/ML scenarios (${MODE}) =="
echo "ROOT_DIR=${ROOT_DIR}"
echo "PYTEST=${PYTEST}"

echo
echo "-- Step 1: synthetic CV/ML gate"
"${ROOT_DIR}/scripts/run-cv-ml-synthetic-checks.sh"

if [[ "${MODE}" == "full" ]]; then
  echo
  echo "-- Step 2: product-slice and mirror/feedback checks"
  cd "${APP_DIR}"
  "${PYTEST}" -q \
    web/tests/test_feedback_loop_service.py \
    web/tests/test_recordings_mirror_ui_api.py
fi

echo
echo "-- Step 3: scenario handoff for hub run"
cat <<'EOF'
Hub-side checklist (when field/hub stage starts):
1) Product-slice smoke:
   scripts/prod/smoke-cv-ml-no-events.sh
2) Re-ID gate from payload snapshots:
   make ml-verify-reid-gates REID_SUMMARY=/tmp/reid_summary.json REID_MATCH=/tmp/reid_match.json REQUIRE_CONTRACT_OK=1
3) Action labeling gate:
   make ml-verify-action-labeling ACTION_EVENTS=/tmp/action_events.json
4) Feedback loop export dry-run:
   curl -X POST /api/ui/system/feedback-loop/export {"dry_run":true,"since_hours":24,"limit":200}
5) NAS mirror connectivity (if configured):
   POST /api/ui/storage/recordings-mirror/test
EOF

echo
echo "CV/ML scenarios: OK"
