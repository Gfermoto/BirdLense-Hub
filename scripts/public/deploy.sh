#!/bin/bash
# Деплой BirdLense Hub
# Локальные настройки (IP, URL) — в scripts/deploy.local.sh (не коммитить)
# Критично: app/data целиком не синхронизируем (как в .github/workflows/deploy.yml) — записи, БД, dataset и images остаются на сервере. Корневой datasets/ (YOLO) не синхронизируем. user_config не перезаписываем.
# Сам следит и исправляет: rsync на сервере, повтор при сбоях

set -euo pipefail

# Загрузить локальные переопределения (создайте из deploy.local.sh.example)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/../deploy.local.sh" ] && . "${SCRIPT_DIR}/../deploy.local.sh"

REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
DEPLOY_URL="${DEPLOY_URL:-http://localhost:8085}"
SYNC_RETRIES="${SYNC_RETRIES:-3}"
# Keepalive — сборка Docker может занимать 5+ мин, без этого SSH обрывается (Broken pipe)
# Порт через DEPLOY_SSH_PORT (по умолчанию 22)
_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"
echo "=== Деплой BirdLense Hub на ${HOST} ==="
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]] && [[ "${DEPLOY_URL}" == *"localhost"* ]]; then
  echo "ВНИМАНИЕ: DEPLOY_URL=${DEPLOY_URL} — health check будет с локальной машины. Для удалённого сервера задайте DEPLOY_URL в deploy.local.sh (например http://YOUR_HOST:8085)"
fi

# 0.4 Опционально (A1 roadmap): прогон verify-prod-env по локальной копии server .env до rsync.
# В deploy.local.sh: RUN_VERIFY_PROD_BEFORE_DEPLOY=1 и при необходимости VERIFY_PROD_ENV_FILE=/path/to/.env
if [[ "${RUN_VERIFY_PROD_BEFORE_DEPLOY:-}" =~ ^(1|true|yes)$ ]]; then
  _vf="${VERIFY_PROD_ENV_FILE:-${REPO_ROOT}/app/.env}"
  if [[ ! -f "$_vf" ]]; then
    echo "Ошибка: RUN_VERIFY_PROD_BEFORE_DEPLOY=1, но файл не найден: $_vf" >&2
    echo "Подсказка: скопируйте app/.env с сервера или задайте VERIFY_PROD_ENV_FILE, либо отключите RUN_VERIFY_PROD_BEFORE_DEPLOY." >&2
    exit 1
  fi
  echo "0.4 verify-prod-env перед деплоем — $_vf"
  (cd "$REPO_ROOT" && VERIFY_PROD_ENV=1 ./scripts/verify-prod-env.sh --env-file "$_vf") || {
    echo "Ошибка: verify-prod-env не прошёл. Исправьте секреты или снимите RUN_VERIFY_PROD_BEFORE_DEPLOY." >&2
    exit 1
  }
fi

# 0.45 Mandatory golden-set gate for model/config changes (#534).
# Gate runs only when changed files hit model/detection-config patterns.
if [[ ! "${BIRDLENSE_SKIP_GOLDEN_SET_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  _gate_base="${GOLDEN_GATE_BASE_REF:-HEAD~1}"
  _gate_head="${GOLDEN_GATE_HEAD_REF:-HEAD}"
  _gate_json="docs/reports/golden_set_gate/golden_set_gate_latest.json"
  _gate_md="docs/reports/golden_set_gate/golden_set_gate_latest.md"
  echo "0.45 Golden Set Mandatory Gate (${_gate_base}..${_gate_head})..."
  (cd "${REPO_ROOT}" && \
    GOLDEN_GATE_MIN_F1="${GOLDEN_GATE_MIN_F1:-0.9}" \
    STRESS_MAX_SILENCE_ACCEPTED="${STRESS_MAX_SILENCE_ACCEPTED:-0}" \
    STRESS_MIN_STORM_RECALL="${STRESS_MIN_STORM_RECALL:-1.0}" \
    python3 ./scripts/enforce_golden_set_gate.py \
      --base-ref "${_gate_base}" \
      --head-ref "${_gate_head}" \
      --out-json "${_gate_json}" \
      --out-md "${_gate_md}" \
      --enforce) || {
        echo "Ошибка: Golden Set Mandatory Gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.46 Error budget release gate (#529).
# Blocks deploy only when budget is exhausted. Override requires reason.
if [[ ! "${BIRDLENSE_SKIP_ERROR_BUDGET_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  _error_budget_json="docs/reports/error_budget_gate/error_budget_gate_latest.json"
  _error_budget_md="docs/reports/error_budget_gate/error_budget_gate_latest.md"
  echo "0.46 Error Budget Gate..."
  if ! (cd "${REPO_ROOT}" && \
    MCP_TOKEN="${MCP_TOKEN:-}" \
    BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON="${BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON:-}" \
    python3 ./scripts/error_budget_gate.py \
      --base-url "${DEPLOY_URL}" \
      --out-json "${_error_budget_json}" \
      --out-md "${_error_budget_md}"); then
    echo "Ошибка: Error Budget Gate не пройден. Деплой остановлен."
    echo "Подсказка: для аварийного обхода задайте BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON."
    exit 1
  fi
fi

# 0.47 Health/readiness/status consistency gate (#530).
if [[ ! "${BIRDLENSE_SKIP_HEALTH_READINESS_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  _hr_json="docs/reports/health_readiness_contract/health_readiness_contract_latest.json"
  _hr_md="docs/reports/health_readiness_contract/health_readiness_contract_latest.md"
  echo "0.47 Health Readiness Contract Gate..."
  (cd "${REPO_ROOT}" && \
    MCP_TOKEN="${MCP_TOKEN:-}" \
    BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    python3 ./scripts/verify_health_readiness_contract.py \
      --base-url "${DEPLOY_URL}" \
      --out-json "${_hr_json}" \
      --out-md "${_hr_md}") || {
        echo "Ошибка: Health/Readiness Contract не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.48 OWASP API controls gate (#531).
if [[ ! "${BIRDLENSE_SKIP_OWASP_API_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  _owasp_json="docs/reports/owasp_api_controls/owasp_api_controls_latest.json"
  _owasp_md="docs/reports/owasp_api_controls/owasp_api_controls_latest.md"
  echo "0.48 OWASP API Controls Gate..."
  (cd "${REPO_ROOT}" && \
    MCP_TOKEN="${MCP_TOKEN:-}" \
    BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    python3 ./scripts/verify_owasp_api_controls.py \
      --base-url "${DEPLOY_URL}" \
      --out-json "${_owasp_json}" \
      --out-md "${_owasp_md}") || {
        echo "Ошибка: OWASP API Controls gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.49 SSDF control map gate (#551).
if [[ ! "${BIRDLENSE_SKIP_SSDF_MAP_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.49 SSDF Control Map Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_ssdf_control_map.py \
      --map-file "docs/reports/ssdf/ssdf_control_map.json" \
      --out-json "docs/reports/ssdf/ssdf_control_map_latest.json" \
      --out-md "docs/reports/ssdf/ssdf_control_map_latest.md") || {
        echo "Ошибка: SSDF Control Map gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.50 Secrets & vulnerability response gate (#552).
if [[ ! "${BIRDLENSE_SKIP_SECRETS_VULN_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.50 Secrets & Vulnerability Response Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_sec_vuln_response.py \
      --vuln-register "docs/reports/security/vulnerability_register.json" \
      --out-json "docs/reports/security/sec_vuln_response_latest.json" \
      --out-md "docs/reports/security/sec_vuln_response_latest.md") || {
        echo "Ошибка: Secrets & Vulnerability gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.51 Runbook coverage gate (#543).
if [[ ! "${BIRDLENSE_SKIP_RUNBOOK_COVERAGE_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.51 Runbook Coverage Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_runbook_coverage.py \
      --catalog "docs/reports/runbook_coverage/incident_catalog.json" \
      --history "docs/reports/runbook_coverage/validation_history.jsonl" \
      --record-validation \
      --out-json "docs/reports/runbook_coverage/runbook_coverage_latest.json" \
      --out-md "docs/reports/runbook_coverage/runbook_coverage_latest.md") || {
        echo "Ошибка: Runbook Coverage gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.52 Deploy idempotency + rollback contract gate (#545).
if [[ ! "${BIRDLENSE_SKIP_DEPLOY_CONTRACT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.52 Deploy Contract Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/report_deploy_contract.py \
      --out-json "docs/reports/deploy_contract/deploy_contract_latest.json" \
      --out-md "docs/reports/deploy_contract/deploy_contract_latest.md") || {
        echo "Ошибка: Deploy Contract gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.53 UI contract integrity gate (#538).
if [[ ! "${BIRDLENSE_SKIP_UI_CONTRACT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.53 UI Contract Guard..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_ui_contract_guard.py \
      --out-json "docs/reports/ui_contract/ui_contract_guard_latest.json" \
      --out-md "docs/reports/ui_contract/ui_contract_guard_latest.md") || {
        echo "Ошибка: UI Contract Guard не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.54 ML drift monitoring + retrain trigger gate (#535).
if [[ ! "${BIRDLENSE_SKIP_ML_DRIFT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.54 ML Drift Trigger Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/report_ml_drift_triggers.py \
      --override-reason "${BIRDLENSE_ML_DRIFT_OVERRIDE_REASON:-}" \
      --out-json "docs/reports/ml_drift/ml_drift_trigger_latest.json" \
      --out-md "docs/reports/ml_drift/ml_drift_trigger_latest.md") || {
        echo "Ошибка: ML Drift Trigger gate не пройден. Деплой остановлен."
        echo "Подсказка: для осознанного bypass задайте BIRDLENSE_ML_DRIFT_OVERRIDE_REASON."
        exit 1
      }
fi

# 0.55 OpenAPI governance gate (#532).
if [[ ! "${BIRDLENSE_SKIP_OPENAPI_GOV_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.55 OpenAPI Governance Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_openapi_governance.py \
      --out-json "docs/reports/openapi_governance/openapi_governance_latest.json" \
      --out-md "docs/reports/openapi_governance/openapi_governance_latest.md") || {
        echo "Ошибка: OpenAPI Governance gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.56 Playwright anti-flake gate (#539).
if [[ ! "${BIRDLENSE_SKIP_PLAYWRIGHT_ANTIFLAKE_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.56 Playwright Anti-Flake Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_playwright_antiflake.py \
      --out-json "docs/reports/e2e_flake/playwright_antiflake_latest.json" \
      --out-md "docs/reports/e2e_flake/playwright_antiflake_latest.md") || {
        echo "Ошибка: Playwright anti-flake gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.57 Critical UX flow suite gate (#540).
if [[ ! "${BIRDLENSE_SKIP_CRITICAL_UX_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.57 Critical UX Suite Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_critical_ux_suite.py \
      --out-json "docs/reports/e2e_critical/critical_ux_suite_latest.json" \
      --out-md "docs/reports/e2e_critical/critical_ux_suite_latest.md") || {
        echo "Ошибка: Critical UX Suite gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.58 Docs Diataxis gate (#541).
if [[ ! "${BIRDLENSE_SKIP_DOCS_DIATAXIS_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.58 Docs Diataxis Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_docs_diataxis.py \
      --out-json "docs/reports/docs_diataxis/docs_diataxis_latest.json" \
      --out-md "docs/reports/docs_diataxis/docs_diataxis_latest.md") || {
        echo "Ошибка: Docs Diataxis gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.59 Docs drift gate (#542).
if [[ ! "${BIRDLENSE_SKIP_DOCS_DRIFT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.59 Docs Drift Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_docs_drift_gate.py \
      --out-json "docs/reports/docs_drift/docs_drift_latest.json" \
      --out-md "docs/reports/docs_drift/docs_drift_latest.md") || {
        echo "Ошибка: Docs Drift gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.60 SLSA build track gate (#546).
if [[ ! "${BIRDLENSE_SKIP_SLSA_BUILD_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.60 SLSA Build Track Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_slsa_build_track.py \
      --out-json "docs/reports/slsa/slsa_build_track_latest.json" \
      --out-md "docs/reports/slsa/slsa_build_track_latest.md") || {
        echo "Ошибка: SLSA Build Track gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.61 Integration contract registry gate (#547).
if [[ ! "${BIRDLENSE_SKIP_INTEGRATION_REGISTRY_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.61 Integration Contract Registry Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_integration_contract_registry.py \
      --out-json "docs/reports/integrations/integration_contract_registry_latest.json" \
      --out-md "docs/reports/integrations/integration_contract_registry_latest.md") || {
        echo "Ошибка: Integration Contract Registry gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.62 Event burst/reconnect resilience gate (#548).
if [[ ! "${BIRDLENSE_SKIP_EVENT_BURST_RECONNECT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.62 Event Burst Reconnect Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_event_burst_reconnect.py \
      --out-json "docs/reports/integrations/event_burst_reconnect_latest.json" \
      --out-md "docs/reports/integrations/event_burst_reconnect_latest.md") || {
        echo "Ошибка: Event Burst/Reconnect gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.63 Scripts ownership/lifecycle gate (#549).
if [[ ! "${BIRDLENSE_SKIP_SCRIPTS_OWNERSHIP_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.63 Scripts Ownership Lifecycle Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_scripts_ownership.py \
      --out-json "docs/reports/tooling/scripts_ownership_latest.json" \
      --out-md "docs/reports/tooling/scripts_ownership_latest.md") || {
        echo "Ошибка: Scripts ownership/lifecycle gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.64 Champion/challenger shadow gate (#536).
if [[ ! "${BIRDLENSE_SKIP_CHAMPION_SHADOW_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.64 Champion Challenger Shadow Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_champion_challenger_shadow.py \
      --out-json "docs/reports/ml_shadow/champion_challenger_latest.json" \
      --out-md "docs/reports/ml_shadow/champion_challenger_latest.md") || {
        echo "Ошибка: Champion/challenger shadow gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.65 ML technical debt scorecard gate (#537).
if [[ ! "${BIRDLENSE_SKIP_ML_TECH_DEBT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.65 ML Technical Debt Scorecard Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_ml_technical_debt_scorecard.py \
      --out-json "docs/reports/ml_debt/ml_technical_debt_scorecard_latest.json" \
      --out-md "docs/reports/ml_debt/ml_technical_debt_scorecard_latest.md") || {
        echo "Ошибка: ML technical debt scorecard gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.66 Review board governance gate (#553).
if [[ ! "${BIRDLENSE_SKIP_REVIEW_BOARD_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.66 Review Board Governance Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_review_board_governance.py \
      --out-json "docs/reports/governance/review_board_latest.json" \
      --out-md "docs/reports/governance/review_board_latest.md") || {
        echo "Ошибка: Review board governance gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.67 Release policy-as-code gate (#554).
if [[ ! "${BIRDLENSE_SKIP_RELEASE_POLICY_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.67 Release Policy As-Code Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_release_policy_as_code.py \
      --out-json "docs/reports/governance/release_policy_latest.json" \
      --out-md "docs/reports/governance/release_policy_latest.md") || {
        echo "Ошибка: Release policy-as-code gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.68 CLI contract standardization gate (#550).
if [[ ! "${BIRDLENSE_SKIP_CLI_CONTRACT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.68 CLI Contract Standardization Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_cli_contract_standardization.py \
      --out-json "docs/reports/tooling/cli_contract_latest.json" \
      --out-md "docs/reports/tooling/cli_contract_latest.md") || {
        echo "Ошибка: CLI contract standardization gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.69 NAS storage contract gate (#350).
if [[ ! "${BIRDLENSE_SKIP_NAS_STORAGE_CONTRACT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.69 NAS Storage Contract Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_nas_storage_contract.py \
      --out-json "docs/reports/storage/nas_storage_contract_latest.json" \
      --out-md "docs/reports/storage/nas_storage_contract_latest.md") || {
        echo "Ошибка: NAS storage contract gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.70 Outcome quality metrics gate (#555/#556).
if [[ ! "${BIRDLENSE_SKIP_OUTCOME_METRICS_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.70 Outcome Quality Metrics Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/report_quality_outcome_metrics.py \
      --db-path "${OUTCOME_DB_PATH:-app/data/db/birdlense.db}" \
      --lookback-hours "${OUTCOME_LOOKBACK_HOURS:-24}" \
      --max-blind-rate "${OUTCOME_MAX_BLIND_RATE:-0.30}" \
      --min-tracks-coverage "${OUTCOME_MIN_TRACKS_COVERAGE:-0.50}" \
      --max-empty-bbox-rate "${OUTCOME_MAX_EMPTY_BBOX_RATE:-0.20}" \
      --min-yolo-frames-with-tracks "${OUTCOME_MIN_YOLO_FRAMES_WITH_TRACKS:-1}" \
      --out-json "docs/reports/quality_outcome/quality_outcome_metrics_latest.json" \
      --out-md "docs/reports/quality_outcome/quality_outcome_metrics_latest.md") || {
        echo "Ошибка: Outcome quality metrics gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0. Остановка контейнера приложения (Redis birdlense-redis не удаляем — кэш переживает пересборку)
echo "0. Остановка контейнера birdlense..."
ssh ${SSH_OPTS} "${HOST}" "docker stop birdlense 2>/dev/null || true; docker rm birdlense 2>/dev/null || true"

# 0.5. Убедиться, что rsync есть на сервере (для надёжной синхронизации)
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  if ! ssh ${SSH_OPTS} "${HOST}" "which rsync" 2>/dev/null; then
    echo "0.5. Установка rsync на сервере..."
    ssh ${SSH_OPTS} "${HOST}" "apt-get update -qq && apt-get install -y rsync"
  fi
fi

# 0.9. Сборка UI локально (обход ETIMEDOUT npm на сервере)
echo "0.9. Сборка UI локально..."
cd "$(dirname "$0")/../.."
node_major=""
if command -v node >/dev/null 2>&1; then
  node_major="$(node -p 'parseInt(process.versions.node.split(".")[0], 10)' 2>/dev/null || true)"
fi
if [[ -z "${node_major}" || "${node_major}" -lt 22 ]]; then
  NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ -s "${NVM_DIR}/nvm.sh" ]; then
    # shellcheck disable=SC1090
    . "${NVM_DIR}/nvm.sh"
    if [ -f "app/ui/.nvmrc" ]; then
      nvm use >/dev/null 2>&1 || nvm install >/dev/null 2>&1 || true
    else
      nvm use 22 >/dev/null 2>&1 || nvm install 22 >/dev/null 2>&1 || true
    fi
  fi
fi
command -v node >/dev/null 2>&1 || { echo "Ошибка: node не найден. Нужен Node.js 22+ для локальной сборки UI (см. app/ui/package.json engines)."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Ошибка: npm не найден. Нужен npm 10+ для локальной сборки UI."; exit 1; }
node_major="$(node -p 'parseInt(process.versions.node.split(".")[0], 10)')"
if [[ "${node_major}" -lt 22 ]]; then
  echo "Ошибка: нужен Node.js 22+ для локальной сборки UI. Сейчас: $(node -v)." >&2
  echo "Подсказка: проверьте app/ui/.nvmrc и выполните: cd app/ui && nvm use" >&2
  exit 1
fi
(cd app/ui && npm ci --no-audit --no-fund && npm run build) || { echo "Ошибка: npm ci / npm run build не удались"; exit 1; }

# 0.95 Бэкап user_config на сервере перед rsync (восстановление: scripts/restore-config.sh или .bak.deploy-*)
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  echo "0.95 Бэкап user_config.yaml на сервере (если есть)..."
  ssh ${SSH_OPTS} "${HOST}" "UC='${REMOTE_DIR}/app/app_config/user_config.yaml'; \
    if [ -f \"\$UC\" ]; then cp \"\$UC\" \"\${UC}.bak.deploy-\$(date +%Y%m%d%H%M%S)\"; echo '  OK: снимок .bak.deploy-*'; fi" || true
fi

# 1. Синхронизация кода (rsync устойчивее к обрывам, повтор при сбое)
echo "1. Синхронизация кода..."
RSYNC_EXCLUDES="--exclude=.git --exclude=node_modules --exclude=__pycache__ --exclude=.env"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=datasets --exclude=app/data --exclude=app/.env"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/app_config/user_config.yaml --exclude=scripts/deploy.local.sh"
# Локальные venv / сборка док — не на сервер
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.venv-docs-tmp --exclude=.venv-docs --exclude=.venv-ci --exclude=site"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/.venv --exclude=.venv-datasets"
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.venv"
# Временный venv для yolo/openvino экспорта (не на сервер; `.venv` без суффикса выше уже исключён)
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.venv-yolo-fetch"
# Локальная песочница проверки не должна попадать на сервер.
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.sandbox"
# Кэши линтера/тестов (часто root после docker compose run) — иначе rsync code 23 Permission denied
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/.ruff_cache --exclude=app/.pytest_cache"
# Локальный build-кэш ESPHome может быть гигабайтным — на сервер Hub не нужен.
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=esphome/.esphome"
# CodeQL CLI, БД и SARIF (scripts/codeql-local.sh) — десятки МБ/ГБ, на хаб не нужны
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.tools"
# Не удалять на сервере: веса .pt, NABirds OpenVINO IR; user_config (exclude + P — двойная страховка от --delete).
RSYNC_FILTER_PROTECT=(
  --filter "P app/processor/models/detection/weights/*.pt"
  --filter "P app/processor/models/detection/weights/best_NABirds_openvino_model/"
  --filter "P app/processor/models/detection/weights/best_NABirds_openvino_model/***"
  --filter "P app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/"
  --filter "P app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/***"
  --filter "P app/processor/models/classification/weights/*.pt"
  --filter "P app/app_config/user_config.yaml"
)
sync_ok=0
for attempt in $(seq 1 ${SYNC_RETRIES}); do
  if [[ "${HOST}" == "localhost" || "${HOST}" == "127.0.0.1" ]]; then
    rsync -a --delete ${RSYNC_EXCLUDES} "${RSYNC_FILTER_PROTECT[@]}" ./ "${REMOTE_DIR}/" && sync_ok=1 && break
  else
    rsync -avz --delete -e "ssh ${SSH_OPTS}" ${RSYNC_EXCLUDES} "${RSYNC_FILTER_PROTECT[@]}" ./ "${HOST}:${REMOTE_DIR}/" && sync_ok=1 && break
  fi
  echo "  Попытка ${attempt}/${SYNC_RETRIES} не удалась, повтор через 5 сек..."
  sleep 5
done
if [[ $sync_ok -eq 0 ]]; then
  echo "Ошибка: синхронизация не удалась после ${SYNC_RETRIES} попыток"
  exit 1
fi
# Предупреждения rsync «cannot delete non-empty directory» — часто лишние каталоги на сервере вне дерева репо; при необходимости удалите вручную по SSH.

# 1.1 Trapper (prod) или legacy NABirds OpenVINO IR
echo "1.1 Проверка весов бинарного детектора..."
if (cd "${REPO_ROOT}" && bash scripts/sync_trapper_weights.sh --check); then
  echo "  TrapperAI @704: OK (локально)"
  if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
    ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}' && bash scripts/sync_trapper_weights.sh --check" || {
      echo "Ошибка: на сервере нет trapper_ai_v02_2024_openvino_model @704." >&2
      exit 1
    }
    echo "  TrapperAI @704: OK (сервер)"
  fi
else
  (cd "${REPO_ROOT}" && bash scripts/sync_detector_weights.sh --check) || {
    echo "Ошибка: нет Trapper @704 и нет best_NABirds OpenVINO." >&2
    echo "  make export-trapper-openvino  или  make export-nabirds-openvino" >&2
    exit 1
  }
  if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
    ssh ${SSH_OPTS} "${HOST}" "cd '${REMOTE_DIR}' && bash scripts/sync_detector_weights.sh --check" || {
      echo "Ошибка: на сервере после rsync нет полного набора весов NABirds OpenVINO." >&2
      exit 1
    }
  fi
fi

# 1.5 Секреты в app/.env
# PROCESSOR_SECRET — всегда задаём (генерируем при отсутствии)
if [ -z "${PROCESSOR_SECRET:-}" ]; then
  PROCESSOR_SECRET=$(openssl rand -hex 16)
  echo "1.5 PROCESSOR_SECRET сгенерирован. Добавьте в deploy.local.sh: export PROCESSOR_SECRET='${PROCESSOR_SECRET}'"
fi
if [ -n "${MCP_TOKEN:-}" ] || [ -n "${PROCESSOR_SECRET:-}" ] || [ -n "${FLASK_SECRET_KEY:-}" ] || [ -n "${BIRDLENSE_ENV:-}" ] || [ -n "${BIRDLENSE_STRICT_API_AUTH:-}" ] || [ -n "${BIRDLENSE_UI_API_KEY:-}" ] || [ -n "${BIRDLENSE_REID_HUB_CACHE_DIR:-}" ]; then
  echo "1.5 Запись секретов в app/.env на сервере (точечная подмена ключей; остальные строки .env сохраняются)..."
  # shellcheck disable=SC2090
  ssh ${SSH_OPTS} "${HOST}" \
    env \
    "REMOTE_DIR=${REMOTE_DIR}" \
    "MCP_TOKEN=${MCP_TOKEN:-}" \
    "PROCESSOR_SECRET=${PROCESSOR_SECRET}" \
    "FLASK_SECRET_KEY=${FLASK_SECRET_KEY:-}" \
    "BIRDLENSE_ENV=${BIRDLENSE_ENV:-}" \
    "BIRDLENSE_STRICT_API_AUTH=${BIRDLENSE_STRICT_API_AUTH:-}" \
    "BIRDLENSE_UI_API_KEY=${BIRDLENSE_UI_API_KEY:-}" \
    "BIRDLENSE_REID_HUB_CACHE_DIR=${BIRDLENSE_REID_HUB_CACHE_DIR:-}" \
    bash -s <<'ENDSSH_MERGE_ENV'
set -euo pipefail
F="${REMOTE_DIR}/app/.env"
mkdir -p "${REMOTE_DIR}/app"
SIZE=$(stat -c%s "$F" 2>/dev/null || echo 0)
if [ ! -f "$F" ] || [ "$SIZE" -gt 1048576 ]; then
  cp "${REMOTE_DIR}/app/.env.example" "$F" 2>/dev/null || touch "$F"
fi
# Удаляем из .env только те ключи, которые сейчас задаём с непустым значением (остальное на сервере не трогаем).
_merge_env_kv() {
  local key="$1" val="$2"
  if [ -z "$val" ] || [ ! -f "$F" ]; then
    return 0
  fi
  grep -v -E "^${key}=" "$F" >"${F}.new" || true
  mv "${F}.new" "$F"
  printf '%s=%s\n' "$key" "$val" >>"$F"
}
_merge_env_kv MCP_TOKEN "${MCP_TOKEN:-}"
_merge_env_kv FLASK_SECRET_KEY "${FLASK_SECRET_KEY:-}"
_merge_env_kv BIRDLENSE_ENV "${BIRDLENSE_ENV:-}"
_merge_env_kv BIRDLENSE_STRICT_API_AUTH "${BIRDLENSE_STRICT_API_AUTH:-}"
_merge_env_kv BIRDLENSE_UI_API_KEY "${BIRDLENSE_UI_API_KEY:-}"
_merge_env_kv BIRDLENSE_REID_HUB_CACHE_DIR "${BIRDLENSE_REID_HUB_CACHE_DIR:-}"
if [ -f "$F" ]; then
  grep -v -E '^PROCESSOR_SECRET=' "$F" >"${F}.new" || true
  mv "${F}.new" "$F"
fi
printf 'PROCESSOR_SECRET=%s\n' "${PROCESSOR_SECRET}" >>"$F"
ENDSSH_MERGE_ENV
fi

# 1.6 Идемпотентные значения в app/.env для production (только если строки ещё не заданы).
# TRUSTED_PROXY=1 — rate limit и логика IP за nginx; CLEANUP — убрать legacy-плейсхолдеры импорта при старте.
# ReID hub cache: фиксируем persistent path в app/data, чтобы torch.hub не грузил DINO заново после каждого деплоя.
echo "1.6b ReID runtime hub cache defaults..."
ssh ${SSH_OPTS} "${HOST}" "F=\"${REMOTE_DIR}/app/.env\"; touch \"\$F\"; \
  mkdir -p \"${REMOTE_DIR}/app/data/reid_hub_cache\"; \
  grep -qE '^BIRDLENSE_REID_HUB_CACHE_DIR=' \"\$F\" || echo 'BIRDLENSE_REID_HUB_CACHE_DIR=/app/data/reid_hub_cache' >> \"\$F\""
if [ "${BIRDLENSE_ENV:-}" = "production" ] && [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  echo "1.6 Production .env defaults (append if missing)..."
  ssh ${SSH_OPTS} "${HOST}" "F=\"${REMOTE_DIR}/app/.env\"; touch \"\$F\"; \
    grep -qE '^TRUSTED_PROXY=' \"\$F\" || echo 'TRUSTED_PROXY=1' >> \"\$F\"; \
    grep -qE '^BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=' \"\$F\" || echo 'BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT=1' >> \"\$F\""
fi

# 1.8 Intel GPU: при наличии renderD* — сгенерировать override (card+render, group_add video/render хоста, sysfs, PERFMON)
# 1.8b PMU / intel_gpu_top: дефолт 3 (и иногда даже 1) режет perf в контейнере при CAP_PERFMON → «Failed to initialize PMU». Значение 0 проверено на VPS; −1 только при необходимости.
echo "1.8 Проверка Intel GPU на сервере..."
ssh ${SSH_OPTS} "${HOST}" "set -e; cd '${REMOTE_DIR}/app' && bash scripts/docker-compose-intel-override-gen.sh; \
  if [ -f docker-compose.override.yml ]; then \
    echo '1.8b sysctl kernel.perf_event_paranoid=0 → /etc/sysctl.d/99-birdlense-perf.conf'; \
    printf '%s\n' 'kernel.perf_event_paranoid=0' > /etc/sysctl.d/99-birdlense-perf.conf; \
    sysctl -p /etc/sysctl.d/99-birdlense-perf.conf || true; \
  fi"

# 1.8c Жёсткий режим: боевой хаб с OpenVINO GPU — на сервере должны быть renderD* и сгенерирован override.
_raw_req="${BIRDLENSE_DEPLOY_REQUIRE_INTEL_GPU:-}"
if [[ "${_raw_req}" =~ ^(1|true|yes|on)$ ]]; then
  echo "1.8c BIRDLENSE_DEPLOY_REQUIRE_INTEL_GPU=${_raw_req} — проверка docker-compose.override.yml на сервере..."
  if ! ssh ${SSH_OPTS} "${HOST}" "test -f '${REMOTE_DIR}/app/docker-compose.override.yml'"; then
    echo "Ошибка: на хосте нет /dev/dri/renderD* или override не создан — OpenVINO GPU в контейнере недоступен."
    echo "  Проверьте Intel iGPU на сервере, драйверы и перезапуск деплоя. Для VPS без GPU не задавайте BIRDLENSE_DEPLOY_REQUIRE_INTEL_GPU."
    exit 1
  fi
  echo "  OK: ${REMOTE_DIR}/app/docker-compose.override.yml есть"
fi

# 2. Сборка и запуск (повтор при сбое — Docker pull, сеть)
echo "2. Сборка и запуск..."
BUILD_RETRIES="${BUILD_RETRIES:-2}"
build_ok=0
for attempt in $(seq 1 ${BUILD_RETRIES}); do
  if ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app/data/recordings ${REMOTE_DIR}/app/data/db ${REMOTE_DIR}/app/app_config && cd ${REMOTE_DIR}/app && make stop 2>/dev/null; make build && make start"; then
    build_ok=1
    break
  fi
  echo "  Сборка/запуск попытка ${attempt}/${BUILD_RETRIES} не удалась, повтор через 10 сек..."
  sleep 10
done
if [[ $build_ok -eq 0 ]]; then
  echo "Предупреждение: сборка/запуск завершились с ошибкой SSH после ${BUILD_RETRIES} попыток; проверяю факт запуска..."
  if ssh ${SSH_OPTS} "${HOST}" "docker ps --filter name=^birdlense$ --format '{{.Status}}' | grep -q '^Up '"; then
    echo "  Контейнер birdlense запущен — продолжаю в режиме пост-проверки."
  else
    echo "Ошибка: сборка/запуск не удались после ${BUILD_RETRIES} попыток"
    exit 1
  fi
fi

# 2.1 user_config на сервере: ключи regen (rsync exclude user_config.yaml).
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  echo "2.1 Идемпотентный merge regen в user_config (если отсутствует track_regen_min_box_size_px)..."
  if ssh ${SSH_OPTS} "${HOST}" "docker exec birdlense python3 /app/scripts/merge_user_config_regen_defaults.py"; then
    echo "  OK"
  else
    echo "  Предупреждение: скрипт merge user_config regen не выполнен (старый образ или контейнер недоступен)."
  fi
fi

# 3. Проверка после деплоя
echo ""
echo "3. Проверка после деплоя..."
sleep 8
echo "  - Docker logs (последние 25 строк):"
ssh ${SSH_OPTS} "${HOST}" "docker logs birdlense --tail=25 2>&1" | tail -30
echo ""
echo "  - Shared verify contract:"
# strict production: /api/ui/status требует Bearer (MCP) или UI key — передаём из deploy.local.sh
DEPLOY_STRICT_QUALITY_REQUIRED="${DEPLOY_STRICT_QUALITY_REQUIRED:-0}"
if [[ "${DEPLOY_STRICT_QUALITY_REQUIRED}" == "1" ]]; then
  echo "  - Strict quality gate: blocking (DEPLOY_STRICT_QUALITY_REQUIRED=1)"
  BASE_URL="${DEPLOY_URL}" ATTEMPTS=20 SLEEP_SEC=3 CHECK_CAMERAS=1 \
    MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    ./scripts/verify-stack.sh --check-domain-health --strict-quality
else
  echo "  - Strict quality gate: report-only (set DEPLOY_STRICT_QUALITY_REQUIRED=1 to block deploy)"
  BASE_URL="${DEPLOY_URL}" ATTEMPTS=20 SLEEP_SEC=3 CHECK_CAMERAS=1 \
    MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    ./scripts/verify-stack.sh --check-domain-health
fi
echo "  - Runtime SLI gate:"
BASE_URL="${DEPLOY_URL}" \
  MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
  MAX_HEARTBEAT_AGE_SECONDS="${MAX_HEARTBEAT_AGE_SECONDS:-240}" \
  MAX_HTTP_OVER_1000MS_RATIO="${MAX_HTTP_OVER_1000MS_RATIO:-0.20}" \
  MIN_HTTP_SAMPLE_COUNT="${MIN_HTTP_SAMPLE_COUNT:-20}" \
  ./scripts/check-runtime-sli.sh --base-url "${DEPLOY_URL}"
echo "  - Runtime performance gate:"
BASE_URL="${DEPLOY_URL}" \
  MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
  python3 ./scripts/perf_gate_runtime.py \
    --base-url "${DEPLOY_URL}" \
    --timeout-sec "${PERF_TIMEOUT_SEC:-20}" \
    --burst-requests "${PERF_BURST_REQUESTS:-120}" \
    --burst-concurrency "${PERF_BURST_CONCURRENCY:-12}" \
    --metrics-scrapes "${PERF_METRICS_SCRAPES:-60}" \
    --metrics-concurrency "${PERF_METRICS_CONCURRENCY:-8}" \
    --soak-seconds "${PERF_SOAK_SECONDS:-20}" \
    --soak-interval-sec "${PERF_SOAK_INTERVAL_SEC:-0.8}" \
    --max-error-rate "${PERF_MAX_ERROR_RATE:-0.02}" \
    --max-p95-ms "${PERF_MAX_P95_MS:-3000}" \
    --max-p99-ms "${PERF_MAX_P99_MS:-5000}" \
    --out "${PERF_OUT:-/tmp/runtime_perf_gate.deploy.v1.json}"
echo "  - DORA snapshot refresh:"
(cd "${REPO_ROOT}" && \
  python3 ./scripts/report_dora_metrics.py \
    --record-deploy \
    --deploy-status success \
    --skip-report && \
  python3 ./scripts/report_dora_metrics.py \
    --window-days "${DORA_WINDOW_DAYS:-28}" \
    --out-json "docs/reports/dora/dora_metrics_latest.json" \
    --out-md "docs/reports/dora/dora_metrics_latest.md")
echo "  - Deploy contract refresh:"
(cd "${REPO_ROOT}" && \
  python3 ./scripts/report_deploy_contract.py \
    --record-run \
    --status success \
    --skip-report && \
  python3 ./scripts/report_deploy_contract.py \
    --out-json "docs/reports/deploy_contract/deploy_contract_latest.json" \
    --out-md "docs/reports/deploy_contract/deploy_contract_latest.md")
echo ""
echo "=== Готово. UI: ${DEPLOY_URL} ==="
echo "Записи и БД не трогаем; user_config.yaml не синхронизируем (есть бэкап .bak.deploy-* перед rsync)."
echo ""
echo "Если API недоступен из браузера: добавьте на сервере в app/.env:"
echo "  CORS_ORIGINS=${DEPLOY_URL}"
echo "(Сейчас без внешнего reverse proxy: тот же origin, что и UI — http://IP:порт; домен/HTTPS позже — обновите URL.)"
