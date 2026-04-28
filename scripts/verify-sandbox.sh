#!/usr/bin/env bash
# Isolated local verification: separate compose project, env, data dir, and port.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT}/app"
SANDBOX_DIR="${SANDBOX_DIR:-${ROOT}/.sandbox/birdlense}"
PORT="${SANDBOX_PORT:-18085}"
PROJECT="${SANDBOX_COMPOSE_PROJECT:-birdlense_sandbox}"
DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

mkdir -p "${SANDBOX_DIR}/data/db" "${SANDBOX_DIR}/data/recordings" "${SANDBOX_DIR}/app_config"
rsync -a --delete --exclude=user_config.yaml "${APP_DIR}/app_config/" "${SANDBOX_DIR}/app_config/"
if [ ! -f "${SANDBOX_DIR}/.env" ]; then
  cat >"${SANDBOX_DIR}/.env" <<EOF
FLASK_SECRET_KEY=sandbox-flask-secret
PROCESSOR_SECRET=sandbox-processor-secret
BIRDLENSE_ENV=production
BIRDLENSE_STRICT_API_AUTH=1
BIRDLENSE_PORT=${PORT}
EOF
fi
cat >"${SANDBOX_DIR}/docker-compose.override.yml" <<EOF
services:
  redis:
    container_name: ${PROJECT}-redis
  birdlense:
    container_name: ${PROJECT}-web
    env_file:
      - ${SANDBOX_DIR}/.env
    environment:
      BIRDLENSE_PORT: "8080"
    volumes:
      - ${SANDBOX_DIR}/data:/app/data
      - ${SANDBOX_DIR}/app_config:/app/app_config
EOF

echo "sandbox: project=${PROJECT} port=${PORT} dir=${SANDBOX_DIR}"
(
  cd "${APP_DIR}"
  if [[ "${DRY_RUN}" == "1" ]]; then
    docker compose -p "${PROJECT}" --env-file "${SANDBOX_DIR}/.env" -f docker-compose.yml -f "${SANDBOX_DIR}/docker-compose.override.yml" config
    exit 0
  fi
  DOCKER_BUILDKIT=1 docker compose -p "${PROJECT}" --env-file "${SANDBOX_DIR}/.env" -f docker-compose.yml -f "${SANDBOX_DIR}/docker-compose.override.yml" build birdlense
  docker compose -p "${PROJECT}" --env-file "${SANDBOX_DIR}/.env" -f docker-compose.yml -f "${SANDBOX_DIR}/docker-compose.override.yml" up -d
)

if [[ "${DRY_RUN}" == "1" ]]; then
  exit 0
fi

BASE_URL="http://127.0.0.1:${PORT}" "${ROOT}/scripts/verify-stack.sh" --attempts 30 --sleep 2

cat <<EOF
sandbox ready: http://127.0.0.1:${PORT}
stop: cd "${APP_DIR}" && docker compose -p "${PROJECT}" --env-file "${SANDBOX_DIR}/.env" -f docker-compose.yml -f "${SANDBOX_DIR}/docker-compose.override.yml" down
EOF
