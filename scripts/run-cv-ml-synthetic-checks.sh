#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/app"

if [[ ! -d "${APP_DIR}" ]]; then
  echo "ERROR: missing app dir: ${APP_DIR}" >&2
  exit 2
fi

if [[ -x "${APP_DIR}/.venv/bin/pytest" ]]; then
  PYTEST="${APP_DIR}/.venv/bin/pytest"
else
  PYTEST="pytest"
fi

echo "== Synthetic CV/ML gate =="
echo "ROOT_DIR=${ROOT_DIR}"
echo "PYTEST=${PYTEST}"

cd "${APP_DIR}"
"${PYTEST}" -q \
  processor/tests/test_binary_paths.py \
  processor/tests/test_notify_preview.py \
  processor/tests/test_mqtt_frigate_geometry_trigger.py \
  processor/tests/test_recording_session.py \
  processor/tests/test_recording_mqtt_window.py \
  processor/tests/test_detection_fusion.py \
  processor/tests/test_reid_import_embeddings_sqlite.py \
  processor/tests/test_verify_reid_production_gates.py \
  processor/tests/test_verify_action_labeling_gates.py \
  web/tests/test_system_file_test_api.py \
  web/tests/test_ml_ops_api.py \
  web/tests/test_detection_quality_baseline_service.py

echo
echo "Synthetic CV/ML gate: OK"
