#!/usr/bin/env bash
# Полный прогон проверок как в .github/workflows/ci-pr.yml (без участия человека).
# По умолчанию без Docker (быстро). Тяжёлый слой как в job docker-tests:
#   CI_FULL_DOCKER=1 ./scripts/ci-full-local.sh
# или: make ci-local-docker
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VENV_CI="${VENV_CI:-$ROOT/.venv-ci}"
VENV_DOCS="${VENV_DOCS:-$ROOT/.venv-docs}"
PYTHON="${PYTHON:-python3}"
CI_FULL_DOCKER="${CI_FULL_DOCKER:-0}"
CI_STRICT_QUALITY_REQUIRED="${CI_STRICT_QUALITY_REQUIRED:-0}"

log() { printf '\n=== %s ===\n' "$*"; }

# Если в неинтерактивном `make` первым в PATH оказался системный Node (<22), подхватить nvm/fnm
# из .nvmrc в app/ui (как в CI setup-node 22). Не вызывает `nvm install` (сеть может быть недоступна).
ci_try_activate_node_22() {
  local major want_major=22
  if command -v node >/dev/null 2>&1; then
    major="$(node -p 'parseInt(process.versions.node.split(".")[0],10)' 2>/dev/null)" || major=0
    if [[ "${major}" -ge "${want_major}" ]]; then
      return 0
    fi
  fi

  local ui_dir="${ROOT}/app/ui"
  local nvm_dir="${NVM_DIR:-${HOME}/.nvm}"

  if [[ -s "${nvm_dir}/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    export NVM_DIR="${nvm_dir}"
    # shellcheck source=/dev/null
    . "${NVM_DIR}/nvm.sh"
    # nvm меняет PATH текущего shell — не в subshell
    pushd "${ui_dir}" >/dev/null || return 1
    nvm use >/dev/null 2>&1 || nvm use 22 >/dev/null 2>&1 || nvm use lts/jod >/dev/null 2>&1 || true
    popd >/dev/null || true
    if command -v node >/dev/null 2>&1; then
      major="$(node -p 'parseInt(process.versions.node.split(".")[0],10)' 2>/dev/null)" || major=0
      if [[ "${major}" -ge "${want_major}" ]]; then
        printf 'ci-full-local: Node через nvm: %s (%s)\n' "$(node -v)" "$(command -v node)" >&2
        return 0
      fi
    fi
  fi

  if command -v fnm >/dev/null 2>&1; then
    # shellcheck disable=SC2312
    eval "$(fnm env 2>/dev/null)" || true
    pushd "${ui_dir}" >/dev/null || return 1
    fnm use >/dev/null 2>&1 || true
    popd >/dev/null || true
    if command -v node >/dev/null 2>&1; then
      major="$(node -p 'parseInt(process.versions.node.split(".")[0],10)' 2>/dev/null)" || major=0
      if [[ "${major}" -ge "${want_major}" ]]; then
        printf 'ci-full-local: Node через fnm: %s (%s)\n' "$(node -v)" "$(command -v node)" >&2
        return 0
      fi
    fi
  fi

  return 1
}

# PYTHONNOUSERSITE: не подмешивать user-site в pytest.
# -u PYTHONPATH: если в окружении PYTHONPATH указывает на ~/.local, pip считает зависимости
#   «уже установленными» и не кладёт их в venv (ломается import под NOUSERSITE).
pip_ci() { env -u PIP_USER -u PYTHONPATH PYTHONNOUSERSITE=1 "${VENV_CI}/bin/python" -m pip "$@"; }
pip_docs() { env -u PIP_USER -u PYTHONPATH PYTHONNOUSERSITE=1 "${VENV_DOCS}/bin/python" -m pip "$@"; }

ensure_venv_ci() {
  if [[ ! -x "${VENV_CI}/bin/python" ]]; then
    log "Создание ${VENV_CI}"
    "${PYTHON}" -m venv "${VENV_CI}"
    pip_ci install -U pip
    pip_ci install -U -r app/web/requirements.txt
    pip_ci install \
      "bandit[toml]==1.8.6" \
      "pip-audit==2.9.0" \
      "ruff==0.9.2" \
      "radon==6.0.1"
  fi
  # Догоняем зависимости в venv (после старых pip-запусков с «битым» PYTHONPATH).
  pip_ci install -q -r "${ROOT}/app/web/requirements.txt"
}

ensure_venv_docs() {
  if [[ ! -x "${VENV_DOCS}/bin/python" ]]; then
    log "Создание ${VENV_DOCS} (MkDocs)"
    "${PYTHON}" -m venv "${VENV_DOCS}"
    pip_docs install -U pip
  fi
  # Догоняем зависимости (частично созданный venv без mkdocs иначе ломает шаг навсегда).
  pip_docs install -q -U -r "${ROOT}/requirements-docs.txt"
}

log "verify-prod-env.sh (A1 CI parity / synthetic secrets)"
SYNTH_SECRET="$(printf 'ci_%029d' 0)"
VERIFY_PROD_ENV=1 BIRDLENSE_STRICT_API_AUTH=1 \
  FLASK_SECRET_KEY="${SYNTH_SECRET}" \
  PROCESSOR_SECRET="${SYNTH_SECRET}" \
  MCP_TOKEN="${SYNTH_SECRET}" \
  "${ROOT}/scripts/verify-prod-env.sh" --require-mcp-token

log "Python: security + ruff + pytest (app/web/tests)"
ensure_venv_ci
(
  cd "${ROOT}/app"
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/bandit" -r web/ processor/src -c bandit.yaml -ll
  # GHSA-r374-rxx8-8654 (paramiko): currently no fixed release in advisory feed.
  # Keep runtime mitigation in code path (RejectPolicy by default) and track upstream advisory updates.
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/pip-audit" -r web/requirements.txt -r processor/requirements.txt \
    --ignore-vuln PYSEC-2022-42969 \
    --ignore-vuln GHSA-r374-rxx8-8654
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/ruff" check web/ processor/src/
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/ruff" format web/ processor/src/ --check
  env -u PIP_USER PYTHONNOUSERSITE=1 PYTHONPATH="${PWD}:${PWD}/web" \
    "${VENV_CI}/bin/python" -m pytest web/tests/ -q --tb=short
)

log "processor: threshold + detector config guards (lightweight)"
(
  cd "${ROOT}/app"
  env -u PIP_USER PYTHONNOUSERSITE=1 PYTHONPATH="${PWD}:${PWD}/processor/src" \
    "${VENV_CI}/bin/python" -m pytest \
    processor/tests/test_threshold_resolution.py \
    processor/tests/test_welfare_runtime.py \
    processor/tests/test_reid_runtime.py \
    processor/tests/test_encoding_utils.py \
    processor/tests/test_decision_trace_builder.py \
    -q --tb=short
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/python" "${ROOT}/scripts/verify_merged_detector_config.py"
)

log "VERSION / docs version"
"${PYTHON}" scripts/check-docs-version.py

log "UI: codegen drift + vitest + typecheck + lint + build"
if ! command -v node >/dev/null 2>&1; then
  ci_try_activate_node_22 || true
fi
if ! command -v node >/dev/null 2>&1; then
  echo "ci-full-local: не найден node. Нужен Node >= 22 (app/ui/package.json engines)." >&2
  exit 1
fi
node_major="$(node -p 'parseInt(process.versions.node.split(".")[0],10)')"
if [[ "${node_major}" -lt 22 ]]; then
  ci_try_activate_node_22 || true
  node_major="$(node -p 'parseInt(process.versions.node.split(".")[0],10)')"
fi
if [[ "${node_major}" -lt 22 ]]; then
  echo "ci-full-local: нужен Node.js >= 22 (как в GitHub Actions). Сейчас: $(node -v) ($(command -v node 2>/dev/null || true))." >&2
  echo "  Установите Node 22+ или выполните в интерактивной оболочке: cd app/ui && nvm use" >&2
  echo "  (скрипт подхватывает ~/.nvm/nvm.sh и app/ui/.nvmrc, если nvm уже установлен)." >&2
  exit 1
fi
(
  cd "${ROOT}/app/ui"
  npm ci
  npm run codegen:openapi
)
git diff --exit-code -- app/ui/src/generated/openapi-types.ts
(
  cd "${ROOT}/app/ui"
  npm run test -- --run
  npm run coverage
  npm run coverage:critical
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
  # MkDocs clean step can fail on stale racey leftovers in site/ from interrupted runs.
  rm -rf "${ROOT}/site"
  "${VENV_DOCS}/bin/python" scripts/check_site_map_meta_paths.py
  "${VENV_DOCS}/bin/mkdocs" build --strict
)

log "Radon (информативно, без падения)"
(
  cd "${ROOT}/app"
  env -u PIP_USER PYTHONNOUSERSITE=1 "${VENV_CI}/bin/radon" cc -a -s web/ processor/src/ || true
)

log "Stream quality matrix gate (#557 Stream E)"
"${PYTHON}" "${ROOT}/scripts/verify_stream_quality_metrics.py" \
  --contract "docs/reports/stream_quality/stream_quality_contract.json" \
  --quality-outcome "docs/reports/quality_outcome/quality_outcome_metrics_latest.json" \
  --favorites-benchmark "docs/reports/favorites_ab_benchmark.json" \
  --champion-shadow "docs/reports/ml_shadow/champion_challenger_latest.json" \
  --out-json "docs/reports/stream_quality/stream_quality_latest.json" \
  --out-md "docs/reports/stream_quality/stream_quality_latest.md"

log "Domain closure package gate (#557 final artifacts)"
"${PYTHON}" "${ROOT}/scripts/verify_domain_closure_package.py" \
  --contract "docs/reports/domain_finetune/closure_package_contract.json" \
  --closure-doc "docs/reports/domain_finetune/closure_package_30_60_90.md" \
  --domain-loop "docs/reports/domain_finetune/domain_finetune_loop_latest.json" \
  --stream-quality "docs/reports/stream_quality/stream_quality_latest.json" \
  --champion-shadow "docs/reports/ml_shadow/champion_challenger_latest.json" \
  --out-json "docs/reports/domain_finetune/closure_package_latest.json" \
  --out-md "docs/reports/domain_finetune/closure_package_latest.md"

log "RC6 golden gates (detector ≠ taxonomy)"
(
  cd "${ROOT}"
  make validate-detector-golden
  make validate-species-golden
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
  if "${ROOT}/scripts/fetch-processor-models-orin.sh"; then
    break
  fi
  sleep $((attempt * 10))
  if [[ "${attempt}" -eq 3 ]]; then
    echo "fetch-processor-models-orin.sh: не удалось после 3 попыток" >&2
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
  if ! curl -sf "${BASE}/api/ui/health" >/dev/null; then
    echo "hub health failed after ${i:-60} attempts" >&2
    exit 1
  fi
  cd e2e
  npm ci
  # По умолчанию только браузер (как в app/Makefile e2e). --with-deps тянет sudo и ломает
  # локальный прогон без passwordless TTY. Нужны системные пакеты: PLAYWRIGHT_INSTALL_DEPS=1 .
  if [[ "${PLAYWRIGHT_INSTALL_DEPS:-0}" == "1" ]]; then
    npx playwright install --with-deps chromium
  else
    npx playwright install chromium
  fi
  env -u NO_COLOR -u FORCE_COLOR NODE_NO_WARNINGS=1 \
    BASE_URL="${BASE}" npx playwright test tests/smoke.spec.ts
  cd "${ROOT}"
  if ! make verify-strict-quality BASE_URL="${BASE}"; then
    if [[ "${CI_STRICT_QUALITY_REQUIRED}" == "1" ]]; then
      echo "verify-strict-quality failed and CI_STRICT_QUALITY_REQUIRED=1" >&2
      exit 1
    fi
    echo "WARN: verify-strict-quality failed on local dataset; continue (CI_STRICT_QUALITY_REQUIRED=0)." >&2
  fi
  python3 scripts/audit_species_cards.py \
    --base-url "${BASE}" \
    --workers 4 \
    --limit 200 \
    --ignore-direct-image-429 \
    --ignore-empty-description \
    --ignore-empty-image-url \
    --report-path .artifacts/catalog-cards-audit.local.json
)

trap - EXIT
cleanup_stack

log "Готово (полный локальный CI с Docker)."
