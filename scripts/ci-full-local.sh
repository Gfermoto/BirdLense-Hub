#!/usr/bin/env bash
# Полный прогон проверок как в .github/workflows/ci-pr.yml (без участия человека).
# По умолчанию без Docker (быстро). Тяжёлый слой как в job docker-tests:
#   CI_FULL_DOCKER=1 ./scripts/ci-full-local.sh
# или: make ci-local-docker
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV_CI="${VENV_CI:-$ROOT/.venv-ci}"
VENV_DOCS="${VENV_DOCS:-$ROOT/.venv-docs}"
PYTHON="${PYTHON:-python3}"
CI_FULL_DOCKER="${CI_FULL_DOCKER:-0}"

log() { printf '\n=== %s ===\n' "$*"; }

ensure_venv_ci() {
  if [[ ! -x "${VENV_CI}/bin/python" ]]; then
    log "Создание ${VENV_CI}"
    "${PYTHON}" -m venv "${VENV_CI}"
    env -u PIP_USER "${VENV_CI}/bin/python" -m pip install -U pip
    env -u PIP_USER "${VENV_CI}/bin/python" -m pip install -U -r app/web/requirements.txt
    env -u PIP_USER "${VENV_CI}/bin/python" -m pip install \
      "bandit[toml]==1.8.6" \
      "pip-audit==2.9.0" \
      "ruff==0.9.2" \
      "radon==6.0.1"
  fi
}

ensure_venv_docs() {
  if [[ ! -x "${VENV_DOCS}/bin/python" ]]; then
    log "Создание ${VENV_DOCS} (MkDocs)"
    "${PYTHON}" -m venv "${VENV_DOCS}"
    env -u PIP_USER "${VENV_DOCS}/bin/python" -m pip install -U pip
    env -u PIP_USER "${VENV_DOCS}/bin/python" -m pip install -U -r requirements-docs.txt
  fi
}

log "Python: security + ruff + pytest (app/web/tests)"
ensure_venv_ci
(
  cd "${ROOT}/app"
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/bandit" -r web/ processor/src -c bandit.yaml -ll
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/pip-audit" -r web/requirements.txt -r processor/requirements.txt \
    --ignore-vuln PYSEC-2022-42969
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/ruff" check web/ processor/src/
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/ruff" format web/ processor/src/ --check
  env -u PIP_USER PYTHONNOUSERSITE=1 PYTHONPATH="${PWD}:${PWD}/web" \
    "${VENV_CI}/bin/python" -m pytest web/tests/ -q --tb=short
)

log "VERSION / docs version"
"${PYTHON}" scripts/check-docs-version.py

log "UI: codegen drift + vitest + typecheck + lint + build"
(
  cd "${ROOT}/app/ui"
  npm ci
  npm run codegen:openapi
)
git diff --exit-code -- app/ui/src/generated/openapi-types.ts
(
  cd "${ROOT}/app/ui"
  npm run test -- --run
  npm run typecheck
  npm run lint
  npm run build
)

log "Settings UI coverage + MkDocs strict"
mkdir -p "${ROOT}/.artifacts"
"${PYTHON}" scripts/check-settings-ui-coverage.py \
  --report-path "${ROOT}/.artifacts/settings-ui-coverage.json" \
  --summary-path "${ROOT}/.artifacts/settings-ui-coverage.md"
ensure_venv_docs
(
  cd "${ROOT}"
  "${VENV_DOCS}/bin/mkdocs" build --strict
)

log "Radon (информативно, без падения)"
(
  cd "${ROOT}/app"
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/radon" cc -a -s web/ processor/src/ || true
)

if [[ "${CI_FULL_DOCKER}" != "1" ]]; then
  log "Docker-слой пропущен (CI_FULL_DOCKER=1 для processor+web тестов в образе и E2E smoke)"
  log "Готово (локальный CI без Docker)."
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "CI_FULL_DOCKER=1, но docker не найден" >&2
  exit 1
fi

cleanup_stack() {
  (cd "${ROOT}/app" && docker compose down) || true
}
trap cleanup_stack EXIT

log "Веса processor (при необходимости)"
for attempt in 1 2 3; do
  if "${ROOT}/scripts/fetch-processor-weights.sh"; then
    break
  fi
  sleep $((attempt * 10))
  if [[ "${attempt}" -eq 3 ]]; then
    echo "fetch-processor-weights.sh: не удалось после 3 попыток" >&2
    exit 1
  fi
done

log "Docker: build + processor unittest + web pytest + E2E smoke"
(
  cd "${ROOT}/app"
  export DOCKER_BUILDKIT=1
  export COMPOSE_DOCKER_CLI_BUILD=1
  test -f .env || cp .env.example .env
  mkdir -p data/db data/recordings
  docker compose build birdlense
  make test
  make test-web
)

(
  cd "${ROOT}/app"
  export BIRDLENSE_PORT="${BIRDLENSE_PORT:-8085}"
  docker compose up -d
  BASE="http://127.0.0.1:${BIRDLENSE_PORT}"
  for i in $(seq 1 60); do
    if curl -sf "${BASE}/api/ui/health" >/dev/null; then
      echo "hub healthy"
      break
    fi
    sleep 2
  done
  curl -sf "${BASE}/api/ui/health" >/dev/null
  cd e2e
  npm ci
  npx playwright install --with-deps chromium
  BASE_URL="${BASE}" npx playwright test tests/smoke.spec.ts
)

trap - EXIT
cleanup_stack

log "Готово (полный локальный CI с Docker)."
