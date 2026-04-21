#!/usr/bin/env bash
# На удалённом хабе: бинарник из zip форка AleksandrRogachev94/BirdLense, классификатор best.pt с HF
# (gfermoto/birdlense-birds-eu), проверка SHA из CHECKSUMS, пересборка birdlense.
#
# Требует: scripts/deploy.local.sh, локальный CHECKSUMS (строка classification/weights/best.pt).
#
# Запуск из корня репо: ./scripts/bootstrap-weights-on-server.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=/dev/null
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:?Set DEPLOY_HOST in scripts/deploy.local.sh}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"

_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=120 -o BatchMode=yes -o ConnectTimeout=20"

EXP="$(awk '/app\/processor\/models\/classification\/weights\/best\.pt$/ {print $1; exit}' "${ROOT}/CHECKSUMS" || true)"
if [ -z "${EXP}" ]; then
  echo "ERROR: нет SHA для classification/weights/best.pt в CHECKSUMS" >&2
  exit 1
fi

CLASSIFIER_URL="${CLASSIFIER_URL:-https://huggingface.co/gfermoto/birdlense-birds-eu/resolve/c6af5aa595cbb1198a61bcf2f3f9c2adc3772dc9/best.pt}"
BINARY_ZIP_URL="${BINARY_ZIP_URL:-https://raw.githubusercontent.com/AleksandrRogachev94/BirdLense/main/app/processor/models/detection/nabirds_yolo11n_binary.zip}"
ZIP_REL="app/processor/models/detection/nabirds_yolo11n_binary.zip"

echo "=== bootstrap weights on ${HOST} (${REMOTE_DIR}) ==="

ssh ${SSH_OPTS} "${HOST}" \
  "REMOTE_DIR='${REMOTE_DIR}'" \
  "EXP_SHA='${EXP}'" \
  "CLASSIFIER_URL='${CLASSIFIER_URL}'" \
  "BINARY_ZIP_URL='${BINARY_ZIP_URL}'" \
  "ZIP_REL='${ZIP_REL}'" \
  bash -s <<'REMOTE'
set -euo pipefail
cd "${REMOTE_DIR}"
mkdir -p app/processor/models/detection/weights app/processor/models/classification/weights
if [ ! -s "${ZIP_REL}" ]; then
  echo "Downloading binary zip (AleksandrRogachev94/BirdLense)..."
  curl -fsSL --retry 4 --retry-connrefused --retry-delay 4 -o "${ZIP_REL}" "${BINARY_ZIP_URL}"
fi
echo "Unzip binary detector..."
unzip -jo "${ZIP_REL}" weights/best.pt -d app/processor/models/detection/weights/

echo "Download EU classifier -> best.pt (gfermoto/birdlense-birds-eu)..."
tmp="$(mktemp)"
curl -fsSL --retry 4 --retry-connrefused --retry-delay 4 -o "${tmp}" "${CLASSIFIER_URL}"
echo "${EXP_SHA}  ${tmp}" | sha256sum -c -
mv "${tmp}" app/processor/models/classification/weights/best.pt
chmod 644 app/processor/models/classification/weights/best.pt
rm -f app/processor/models/classification/weights/best_EU.pt

echo "Files:"
ls -la app/processor/models/detection/weights/best.pt app/processor/models/classification/weights/best.pt

echo "Docker rebuild (no cache for birdlense)..."
cd app
docker compose build --no-cache birdlense
docker compose up -d birdlense
echo "OK: birdlense перезапущен."
REMOTE

echo "=== готово ==="
