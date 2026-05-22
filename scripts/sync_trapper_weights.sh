#!/usr/bin/env bash
# Проверка Trapper PT + OpenVINO @704 и опциональный rsync на VPS (deploy.local.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WEIGHTS="${WEIGHTS_DIR:-${REPO_ROOT}/app/processor/models/detection/weights}"
PT="${WEIGHTS}/trapper_ai_v02_2024.pt"
OV="${WEIGHTS}/trapper_ai_v02_2024_openvino_model"
RSYNC_VPS=0

usage() {
  cat <<'EOF'
Usage: sync_trapper_weights.sh [--check] [--rsync-vps]

  --check       только проверка локально (exit 1 если нет IR @704)
  --rsync-vps   после check — rsync PT + OV на DEPLOY_HOST (нужен scripts/deploy.local.sh)
EOF
}

CHECK_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --rsync-vps) RSYNC_VPS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

missing=()
[[ -f "${PT}" ]] || missing+=("${PT}")
[[ -f "${OV}/best.xml" ]] || missing+=("${OV}/best.xml")
[[ -f "${OV}/best.bin" ]] || missing+=("${OV}/best.bin")
[[ -f "${OV}/metadata.yaml" ]] || missing+=("${OV}/metadata.yaml")

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "sync_trapper_weights: missing:" >&2
  printf '  %s\n' "${missing[@]}" >&2
  echo "  make export-trapper-openvino  (или docker compose run -v repo:/repo ... export_trapper_to_openvino.py)" >&2
  exit 1
fi

if ! grep -qE '^- 704$' "${OV}/metadata.yaml" 2>/dev/null; then
  echo "sync_trapper_weights: metadata.yaml imgsz != 704 — переэкспорт: make export-trapper-openvino" >&2
  exit 1
fi

echo "sync_trapper_weights: OK local (${OV}, imgsz=704)"
sha256sum "${PT}" "${OV}/best.bin" "${OV}/metadata.yaml"

if [[ "${RSYNC_VPS}" != "1" ]]; then
  exit 0
fi

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/deploy.local.sh"
PORT="${DEPLOY_SSH_PORT:-22}"
RSYNC_SSH="ssh -p ${PORT}"
REMOTE="${DEPLOY_HOST}:${DEPLOY_REMOTE_DIR}/app/processor/models/detection/weights"

echo "== rsync Trapper → VPS =="
rsync -avz --delete -e "${RSYNC_SSH}" "${OV}/" "${REMOTE}/trapper_ai_v02_2024_openvino_model/"
rsync -avz -e "${RSYNC_SSH}" "${PT}" "${REMOTE}/"
ssh -p "${PORT}" "${DEPLOY_HOST}" "grep -A2 '^imgsz:' ${DEPLOY_REMOTE_DIR}/app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/metadata.yaml"
echo "sync_trapper_weights: VPS OK"
