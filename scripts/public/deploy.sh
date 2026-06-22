#!/bin/bash
# Деплой BirdLense Hub
# Локальные настройки (IP, URL) — в scripts/deploy.local.sh (не коммитить)
# Критично: app/data целиком не синхронизируем (как в .github/workflows/deploy.yml) — записи, БД, dataset и images остаются на сервере. Корневой datasets/ (YOLO) не синхронизируем. user_config не перезаписываем.
# Сам следит и исправляет: rsync на сервере, повтор при сбоях

set -euo pipefail

# Загрузить локальные переопределения (создайте из deploy.local.sh.example)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/../deploy.local.sh" ] && . "${SCRIPT_DIR}/../deploy.local.sh"
# shellcheck source=../platform-profile.sh
. "${SCRIPT_DIR}/../platform-profile.sh"
BIRDLENSE_PLATFORM="$(birdlense_normalize_platform)" || exit 1
export BIRDLENSE_PLATFORM

REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
DEPLOY_URL="${DEPLOY_URL:-http://localhost:8085}"
SYNC_RETRIES="${SYNC_RETRIES:-3}"
DEPLOY_MIN_INTERVAL_MINUTES="${DEPLOY_MIN_INTERVAL_MINUTES:-20}"
DEPLOY_MIN_INTERVAL_BYPASS="${DEPLOY_MIN_INTERVAL_BYPASS:-0}"
DEPLOY_MIN_FREE_GB="${DEPLOY_MIN_FREE_GB:-5}"
DEPLOY_MAX_DIAGNOSTICS_GB_WARN="${DEPLOY_MAX_DIAGNOSTICS_GB_WARN:-2}"
OUTCOME_DB_MODE="${OUTCOME_DB_MODE:-auto}"  # auto|local|remote
OUTCOME_DB_PATH="${OUTCOME_DB_PATH:-app/data/db/birdlense.db}"
OUTCOME_REMOTE_DB_PATH="${OUTCOME_REMOTE_DB_PATH:-${REMOTE_DIR}/app/data/db/birdlense.db}"
OUTCOME_LOOKBACK_HOURS="${OUTCOME_LOOKBACK_HOURS:-24}"
OUTCOME_MAX_BLIND_RATE="${OUTCOME_MAX_BLIND_RATE:-0.30}"
OUTCOME_MIN_TRACKS_COVERAGE="${OUTCOME_MIN_TRACKS_COVERAGE:-0.50}"
OUTCOME_MAX_EMPTY_BBOX_RATE="${OUTCOME_MAX_EMPTY_BBOX_RATE:-0.20}"
OUTCOME_MIN_YOLO_FRAMES_WITH_TRACKS="${OUTCOME_MIN_YOLO_FRAMES_WITH_TRACKS:-1}"
OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE="${OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE:-0.10}"
OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE_DELTA_VS_7D="${OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE_DELTA_VS_7D:-0.08}"

_gate_json_hub_unreachable() {
  local json_path="$1"
  local key="${2:-hub_unreachable}"
  python3 - "$json_path" "$key" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
if not path.is_file():
    raise SystemExit(0)
data = json.loads(path.read_text(encoding="utf-8"))
if bool(data.get(key)):
    raise SystemExit(0)
gate = data.get("gate")
if isinstance(gate, dict) and bool(gate.get(key)):
    raise SystemExit(0)
inputs = data.get("inputs")
if isinstance(inputs, dict) and bool(inputs.get(key)):
    raise SystemExit(0)
raise SystemExit(1)
PY
}

_outcome_use_local_db() {
  if [[ "${OUTCOME_DB_MODE}" == "local" ]]; then
    return 0
  fi
  if [[ "${OUTCOME_DB_MODE}" == "remote" ]]; then
    return 1
  fi
  # auto: локальная БД только для localhost; VPS — remote DB на сервере
  if [[ "${HOST}" == "localhost" || "${HOST}" == "127.0.0.1" ]]; then
    [[ -f "${REPO_ROOT}/${OUTCOME_DB_PATH}" ]]
    return
  fi
  return 1
}
# Keepalive — сборка Docker может занимать 5+ мин, без этого SSH обрывается (Broken pipe)
# Порт через DEPLOY_SSH_PORT (по умолчанию 22)
_PORT_OPT=""
_SCP_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
  _SCP_PORT_OPT="-P ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"
SCP_OPTS="${_SCP_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"
echo "=== Деплой BirdLense Hub на ${HOST} (platform=${BIRDLENSE_PLATFORM}) ==="
if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]] && [[ "${DEPLOY_URL}" == *"localhost"* ]]; then
  echo "ВНИМАНИЕ: DEPLOY_URL=${DEPLOY_URL} — health check будет с локальной машины. Для удалённого сервера задайте DEPLOY_URL в deploy.local.sh (например http://YOUR_HOST:8085)"
fi
if [[ ! "${DEPLOY_MIN_INTERVAL_BYPASS}" =~ ^(1|true|yes)$ ]] && [[ "${DEPLOY_MIN_INTERVAL_MINUTES}" =~ ^[0-9]+$ ]] && [ "${DEPLOY_MIN_INTERVAL_MINUTES}" -gt 0 ]; then
  _deploy_events="${REPO_ROOT}/docs/reports/dora/deploy_events.jsonl"
  if ! python3 - "$_deploy_events" "${DEPLOY_MIN_INTERVAL_MINUTES}" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

events_path = Path(sys.argv[1])
min_interval_minutes = int(sys.argv[2])
if not events_path.exists():
    raise SystemExit(0)
last_success = None
for line in events_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        continue
    if str(row.get("status") or "").strip().lower() != "success":
        continue
    ts = str(row.get("deployed_at") or "").strip()
    if not ts:
        continue
    try:
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        continue
    if last_success is None or dt > last_success:
        last_success = dt
if last_success is None:
    raise SystemExit(0)
minutes = (datetime.now(UTC) - last_success).total_seconds() / 60.0
if minutes < float(min_interval_minutes):
    print(
        "Deploy cooldown active: "
        f"{minutes:.1f}m since last success < {min_interval_minutes}m threshold."
    )
    raise SystemExit(2)
PY
  then
    echo "Ошибка: деплой остановлен политикой cooldown, чтобы не терять визиты на частых перезапусках."
    echo "Подсказка: подождите или выставьте DEPLOY_MIN_INTERVAL_BYPASS=1 для аварийного исключения."
    exit 1
  fi
fi

check_remote_disk_headroom() {
  local host="$1"
  local remote_dir="$2"
  local min_free_gb="$3"
  local diagnostics_warn_gb="$4"
  ssh ${SSH_OPTS} "${host}" "python3 - <<'PY'
import os
import shutil
from pathlib import Path

root = Path('/')
remote_dir = Path('${remote_dir}')
data_dir = remote_dir / 'app' / 'data'
diag_dir = data_dir / 'diagnostics'
min_free_gb = float('${min_free_gb}')
warn_diag_gb = float('${diagnostics_warn_gb}')

usage = shutil.disk_usage(str(root))
free_gb = usage.free / (1024 ** 3)
used_pct = (usage.used / usage.total) * 100.0 if usage.total else 0.0
print(f'disk-check: free_gb={free_gb:.2f} used_pct={used_pct:.2f}')

diag_bytes = 0
if diag_dir.exists():
    for p in diag_dir.rglob('*'):
        if p.is_file():
            try:
                diag_bytes += p.stat().st_size
            except OSError:
                pass
diag_gb = diag_bytes / (1024 ** 3)
print(f'disk-check: diagnostics_gb={diag_gb:.2f}')

if diag_gb > warn_diag_gb:
    print(
        'disk-check: WARN diagnostics size high; '
        f'consider cleanup or disabling debug dumps (threshold={warn_diag_gb:.2f}GB)'
    )

if free_gb < min_free_gb:
    print(
        'disk-check: FAIL low free disk space; '
        f'free={free_gb:.2f}GB threshold={min_free_gb:.2f}GB'
    )
    raise SystemExit(2)
PY"
}

if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
  echo "0.0 Проверка свободного места на сервере..."
  if ! check_remote_disk_headroom "${HOST}" "${REMOTE_DIR}" "${DEPLOY_MIN_FREE_GB}" "${DEPLOY_MAX_DIAGNOSTICS_GB_WARN}"; then
    echo "Ошибка: недостаточно свободного места на сервере для безопасного деплоя."
    echo "Подсказка: освободите место или временно уменьшите DEPLOY_MIN_FREE_GB."
    exit 1
  fi
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

# 0.43 Processor config drift on prod user_config (blocking on critical, #626).
if [[ ! "${BIRDLENSE_SKIP_CONFIG_DRIFT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]] && \
     [[ -f "${REPO_ROOT}/scripts/verify-prod-config-drift.sh" ]]; then
    echo "0.43 Processor config drift (prod user_config, critical blocking)..."
    if ! (cd "${REPO_ROOT}" && chmod +x ./scripts/verify-prod-config-drift.sh && \
          ./scripts/verify-prod-config-drift.sh); then
      echo "ERROR: critical prod processor config drift — deploy blocked (#626)." >&2
      echo "Подсказка: make verify-prod-config-drift; BIRDLENSE_SKIP_CONFIG_DRIFT_GATE=1 to skip." >&2
      exit 1
    fi
  fi
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
_ERROR_BUDGET_HUB_UNREACHABLE=0
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
  if _gate_json_hub_unreachable "${REPO_ROOT}/${_error_budget_json}"; then
    _ERROR_BUDGET_HUB_UNREACHABLE=1
    echo "  WARN: Error Budget Gate — hub unreachable pre-deploy; повтор после health contract."
  fi
fi

# 0.48 OWASP API controls gate (#531).
_OWASP_HUB_UNREACHABLE=0
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
  if _gate_json_hub_unreachable "${REPO_ROOT}/${_owasp_json}"; then
    _OWASP_HUB_UNREACHABLE=1
    echo "  WARN: OWASP API Controls — hub unreachable pre-deploy; повтор после health contract."
  fi
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

# 0.70 Dataset contract registry gate (#557 Stream A).
if [[ ! "${BIRDLENSE_SKIP_DATASET_CONTRACT_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.70 Dataset Contract Registry Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_dataset_contract_registry.py \
      --contract "docs/reports/datasets/dataset_contract_registry.json" \
      --out-json "docs/reports/datasets/dataset_contract_registry_latest.json" \
      --out-md "docs/reports/datasets/dataset_contract_registry_latest.md") || {
        echo "Ошибка: Dataset contract registry gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.71 Domain fine-tune loop evidence gate (#557 Stream C).
if [[ ! "${BIRDLENSE_SKIP_DOMAIN_FINETUNE_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.71 Domain Fine-tune Loop Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_domain_finetune_loop.py \
      --contract "docs/reports/domain_finetune/domain_finetune_contract.json" \
      --champion-shadow "docs/reports/ml_shadow/champion_challenger_latest.json" \
      --acceptance-gate "docs/reports/golden_set_gate/golden_set_gate_latest.json" \
      --history "docs/reports/ml_shadow/shadow_pipeline_history.jsonl" \
      --out-json "docs/reports/domain_finetune/domain_finetune_loop_latest.json" \
      --out-md "docs/reports/domain_finetune/domain_finetune_loop_latest.md") || {
        echo "Ошибка: Domain fine-tune loop gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.72 Outcome quality metrics gate (#555/#556).
if [[ ! "${BIRDLENSE_SKIP_OUTCOME_METRICS_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.72 Outcome Quality Metrics Gate..."
  if _outcome_use_local_db; then
    (cd "${REPO_ROOT}" && \
      python3 ./scripts/report_quality_outcome_metrics.py \
        --db-path "${OUTCOME_DB_PATH}" \
        --data-source "local:${OUTCOME_DB_PATH}" \
        --lookback-hours "${OUTCOME_LOOKBACK_HOURS}" \
        --max-blind-rate "${OUTCOME_MAX_BLIND_RATE}" \
        --min-tracks-coverage "${OUTCOME_MIN_TRACKS_COVERAGE}" \
        --max-empty-bbox-rate "${OUTCOME_MAX_EMPTY_BBOX_RATE}" \
        --min-yolo-frames-with-tracks "${OUTCOME_MIN_YOLO_FRAMES_WITH_TRACKS}" \
        --max-frigate-catches-missed-birds-rate "${OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE}" \
        --max-frigate-catches-missed-birds-rate-delta-vs-7d "${OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE_DELTA_VS_7D}" \
        --out-json "docs/reports/quality_outcome/quality_outcome_metrics_latest.json" \
        --out-md "docs/reports/quality_outcome/quality_outcome_metrics_latest.md") || {
          echo "Ошибка: Outcome quality metrics gate (local DB) не пройден. Деплой остановлен."
          exit 1
        }
  else
    if [[ "${OUTCOME_DB_MODE}" != "remote" ]] && [[ "${OUTCOME_DB_MODE}" != "auto" ]]; then
      echo "Ошибка: неизвестный OUTCOME_DB_MODE=${OUTCOME_DB_MODE}" >&2
      exit 1
    fi
    echo "  - outcome gate на удалённой БД (${HOST})"
    ssh ${SSH_OPTS} "${HOST}" \
      "cd '${REMOTE_DIR}' && python3 ./scripts/report_quality_outcome_metrics.py \
        --db-path '${OUTCOME_REMOTE_DB_PATH}' \
        --data-source 'remote:${HOST}:${OUTCOME_REMOTE_DB_PATH}' \
        --lookback-hours '${OUTCOME_LOOKBACK_HOURS}' \
        --max-blind-rate '${OUTCOME_MAX_BLIND_RATE}' \
        --min-tracks-coverage '${OUTCOME_MIN_TRACKS_COVERAGE}' \
        --max-empty-bbox-rate '${OUTCOME_MAX_EMPTY_BBOX_RATE}' \
        --min-yolo-frames-with-tracks '${OUTCOME_MIN_YOLO_FRAMES_WITH_TRACKS}' \
        --max-frigate-catches-missed-birds-rate '${OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE}' \
        --max-frigate-catches-missed-birds-rate-delta-vs-7d '${OUTCOME_MAX_FRIGATE_CATCHES_MISSED_BIRDS_RATE_DELTA_VS_7D}' \
        --out-json 'docs/reports/quality_outcome/quality_outcome_metrics_latest.json' \
        --out-md 'docs/reports/quality_outcome/quality_outcome_metrics_latest.md'" || {
          echo "Ошибка: Outcome quality metrics gate (remote DB) не пройден. Деплой остановлен."
          exit 1
        }
    mkdir -p "${REPO_ROOT}/docs/reports/quality_outcome"
    scp ${SCP_OPTS} \
      "${HOST}:${REMOTE_DIR}/docs/reports/quality_outcome/quality_outcome_metrics_latest.json" \
      "${REPO_ROOT}/docs/reports/quality_outcome/quality_outcome_metrics_latest.json"
    scp ${SCP_OPTS} \
      "${HOST}:${REMOTE_DIR}/docs/reports/quality_outcome/quality_outcome_metrics_latest.md" \
      "${REPO_ROOT}/docs/reports/quality_outcome/quality_outcome_metrics_latest.md" 2>/dev/null || true
  fi
fi

# 0.73 Stream quality matrix gate (#557 Stream E).
if [[ ! "${BIRDLENSE_SKIP_STREAM_QUALITY_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.73 Stream Quality Matrix Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_stream_quality_metrics.py \
      --contract "docs/reports/stream_quality/stream_quality_contract.json" \
      --quality-outcome "docs/reports/quality_outcome/quality_outcome_metrics_latest.json" \
      --favorites-benchmark "docs/reports/favorites_ab_benchmark.json" \
      --champion-shadow "docs/reports/ml_shadow/champion_challenger_latest.json" \
      --out-json "docs/reports/stream_quality/stream_quality_latest.json" \
      --out-md "docs/reports/stream_quality/stream_quality_latest.md") || {
        echo "Ошибка: Stream quality matrix gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0.74 Domain closure package gate (#557 final artifacts).
if [[ ! "${BIRDLENSE_SKIP_DOMAIN_CLOSURE_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "0.74 Domain Closure Package Gate..."
  (cd "${REPO_ROOT}" && \
    python3 ./scripts/verify_domain_closure_package.py \
      --contract "docs/reports/domain_finetune/closure_package_contract.json" \
      --closure-doc "docs/reports/domain_finetune/closure_package_30_60_90.md" \
      --domain-loop "docs/reports/domain_finetune/domain_finetune_loop_latest.json" \
      --stream-quality "docs/reports/stream_quality/stream_quality_latest.json" \
      --champion-shadow "docs/reports/ml_shadow/champion_challenger_latest.json" \
      --out-json "docs/reports/domain_finetune/closure_package_latest.json" \
      --out-md "docs/reports/domain_finetune/closure_package_latest.md") || {
        echo "Ошибка: Domain closure package gate не пройден. Деплой остановлен."
        exit 1
      }
fi

# 0. Остановка контейнера birdlense + удаление старого образа (Redis birdlense-redis не трогаем)
echo "0. Остановка birdlense и удаление старых образов app-birdlense..."
ssh ${SSH_OPTS} "${HOST}" "set -e; \
  cd '${REMOTE_DIR}/app' 2>/dev/null || cd '${REMOTE_DIR}'; \
  if [ -f docker-compose.yml ]; then \
    docker compose stop birdlense 2>/dev/null || true; \
    docker compose rm -f birdlense 2>/dev/null || true; \
  fi; \
  docker stop birdlense 2>/dev/null || true; \
  docker rm birdlense 2>/dev/null || true; \
  old_images=\$(docker images -q 'app-birdlense' 2>/dev/null || true); \
  if [ -n \"\${old_images}\" ]; then \
    echo \"  docker rmi app-birdlense: \${old_images}\"; \
    docker rmi -f \${old_images} || true; \
  fi; \
  docker image prune -f --filter 'dangling=true' 2>/dev/null || true"

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
if [[ -f app/ui/dist/index.html ]]; then
  echo "  Using pre-built UI dist (app/ui/dist/index.html)"
else
  if [[ "${BIRDLENSE_SKIP_LOCAL_UI_NPM_CI:-}" =~ ^(1|true|yes)$ ]]; then
    (cd app/ui && npm run build) || { echo "Ошибка: npm run build не удался (SKIP_LOCAL_UI_NPM_CI=1)"; exit 1; }
  else
    (cd app/ui && npm ci --no-audit --no-fund && npm run build) || { echo "Ошибка: npm ci / npm run build не удались"; exit 1; }
  fi
fi

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
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=.venv --exclude=.venv-birder"
# Модели и веса — внутри Docker-образа, не нужно на сервере
RSYNC_EXCLUDES="$RSYNC_EXCLUDES --exclude=app/processor/models"
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
# Не удалять на сервере: user_config (exclude + P — двойная страховка от --delete).
RSYNC_FILTER_PROTECT=(
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

# 1.05 Каталог кормов (app/data целиком исключён — иначе на сервере нулевые JPG в образе и entrypoint затирает volume).
if [[ -d "${REPO_ROOT}/app/data/images" ]]; then
  echo "1.05 Синхронизация catalog images (food и т.д.)..."
  if [[ "${HOST}" == "localhost" || "${HOST}" == "127.0.0.1" ]]; then
    rsync -a "${REPO_ROOT}/app/data/images/" "${REMOTE_DIR}/app/data/images/"
  else
    rsync -avz -e "ssh ${SSH_OPTS}" "${REPO_ROOT}/app/data/images/" "${HOST}:${REMOTE_DIR}/app/data/images/"
  fi
fi

# 1.1 Trapper (prod) или legacy NABirds OpenVINO IR — только intel_nuc; Jetson: .pt без IR
echo "1.1 Проверка весов бинарного детектора..."
_check_pt_only_weights() {
  local w="${REPO_ROOT}/app/processor/models/detection/weights"
  local pt=""
  if [[ -f "${w}/trapper_ai_v02_2024.pt" ]]; then
    pt="${w}/trapper_ai_v02_2024.pt"
  elif [[ -f "${w}/best_NABirds.pt" ]]; then
    pt="${w}/best_NABirds.pt"
  elif [[ -f "${w}/best.pt" ]]; then
    pt="${w}/best.pt"
  fi
  if [[ -z "${pt}" ]]; then
    echo "Ошибка: для Jetson нужен хотя бы один .pt в app/processor/models/detection/weights/" >&2
    return 1
  fi
  echo "  Jetson PT-only: OK local (${pt})"
  if [[ "${HOST}" != "localhost" && "${HOST}" != "127.0.0.1" ]]; then
    ssh ${SSH_OPTS} "${HOST}" "w='${REMOTE_DIR}/app/processor/models/detection/weights'; \
      for f in trapper_ai_v02_2024.pt best_NABirds.pt best.pt; do test -f \"\${w}/\${f}\" && exit 0; done; exit 1" || {
      echo "Ошибка: на сервере нет .pt детектора для Jetson." >&2
      return 1
    }
    echo "  Jetson PT-only: OK (сервер)"
  fi
}
if birdlense_platform_is_jetson; then
  _check_pt_only_weights || exit 1
else
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
fi

# 1.5 Секреты в app/.env
# PROCESSOR_SECRET — всегда задаём (генерируем при отсутствии)
if [ -z "${PROCESSOR_SECRET:-}" ]; then
  PROCESSOR_SECRET=$(openssl rand -hex 16)
  echo "1.5 PROCESSOR_SECRET сгенерирован. Добавьте в deploy.local.sh: export PROCESSOR_SECRET='${PROCESSOR_SECRET}'"
fi
if [ -n "${MCP_TOKEN:-}" ] || [ -n "${PROCESSOR_SECRET:-}" ] || [ -n "${FLASK_SECRET_KEY:-}" ] || [ -n "${BIRDLENSE_ENV:-}" ] || [ -n "${BIRDLENSE_STRICT_API_AUTH:-}" ] || [ -n "${BIRDLENSE_UI_API_KEY:-}" ] || [ -n "${BIRDLENSE_REID_HUB_CACHE_DIR:-}" ] || [ -n "${BIRDLENSE_PLATFORM:-}" ]; then
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
    "BIRDLENSE_PLATFORM=${BIRDLENSE_PLATFORM:-}" \
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
_merge_env_kv BIRDLENSE_PLATFORM "${BIRDLENSE_PLATFORM:-}"
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

# 1.8 Intel GPU: при наличии renderD* — сгенерировать override (пропуск для jetson_nano)
if ! birdlense_platform_is_jetson; then
echo "1.8 Проверка Intel GPU на сервере..."
ssh ${SSH_OPTS} "${HOST}" "set -e; cd '${REMOTE_DIR}/app' && bash scripts/docker-compose-intel-override-gen.sh; \
  if [ -f docker-compose.override.yml ]; then \
    echo '1.8b sysctl kernel.perf_event_paranoid=0 → /etc/sysctl.d/99-birdlense-perf.conf'; \
    printf '%s\n' 'kernel.perf_event_paranoid=0' > /etc/sysctl.d/99-birdlense-perf.conf; \
    sysctl -p /etc/sysctl.d/99-birdlense-perf.conf || true; \
  fi"
else
  echo "1.8 Intel GPU override: пропуск (platform=jetson_nano)"
  ssh ${SSH_OPTS} "${HOST}" "rm -f '${REMOTE_DIR}/app/docker-compose.override.yml' 2>/dev/null || true"
fi

# 1.8c Жёсткий режим: боевой хаб с OpenVINO GPU — на сервере должны быть renderD* и сгенерирован override.
_raw_req="${BIRDLENSE_DEPLOY_REQUIRE_INTEL_GPU:-}"
if [[ "${_raw_req}" =~ ^(1|true|yes|on)$ ]] && ! birdlense_platform_is_jetson; then
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
  if ssh ${SSH_OPTS} "${HOST}" "mkdir -p ${REMOTE_DIR}/app/data/recordings ${REMOTE_DIR}/app/data/db ${REMOTE_DIR}/app/app_config && cd ${REMOTE_DIR}/app && \
    old_images=\$(docker images -q 'app-birdlense' 2>/dev/null || true); \
    if [ -n \"\${old_images}\" ]; then docker rmi -f \${old_images} || true; fi; \
    BIRDLENSE_PLATFORM='${BIRDLENSE_PLATFORM}' make stop 2>/dev/null; BIRDLENSE_PLATFORM='${BIRDLENSE_PLATFORM}' make build && BIRDLENSE_PLATFORM='${BIRDLENSE_PLATFORM}' make start"; then
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
# OpenVINO/bootstrap может занимать 3–5 мин; readiness retry — в verify-stack (ATTEMPTS×SLEEP_SEC).
DEPLOY_READINESS_ATTEMPTS="${DEPLOY_READINESS_ATTEMPTS:-60}"
DEPLOY_READINESS_SLEEP_SEC="${DEPLOY_READINESS_SLEEP_SEC:-5}"
echo "  - Post-deploy readiness wait: up to $((DEPLOY_READINESS_ATTEMPTS * DEPLOY_READINESS_SLEEP_SEC))s (${DEPLOY_READINESS_ATTEMPTS}×${DEPLOY_READINESS_SLEEP_SEC}s)"
echo "  - Docker logs (последние 25 строк):"
ssh ${SSH_OPTS} "${HOST}" "docker logs birdlense --tail=25 2>&1" | tail -30
echo ""
echo "  - Shared verify contract:"
# strict production: /api/ui/status требует Bearer (MCP) или UI key — передаём из deploy.local.sh
DEPLOY_STRICT_QUALITY_REQUIRED="${DEPLOY_STRICT_QUALITY_REQUIRED:-0}"
if [[ "${DEPLOY_STRICT_QUALITY_REQUIRED}" == "1" ]]; then
  echo "  - Strict quality gate: blocking (DEPLOY_STRICT_QUALITY_REQUIRED=1)"
  BASE_URL="${DEPLOY_URL}" ATTEMPTS="${DEPLOY_READINESS_ATTEMPTS}" SLEEP_SEC="${DEPLOY_READINESS_SLEEP_SEC}" CHECK_CAMERAS=1 \
    MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    ./scripts/verify-stack.sh --check-domain-health --strict-quality
else
  echo "  - Strict quality gate: report-only (set DEPLOY_STRICT_QUALITY_REQUIRED=1 to block deploy)"
  BASE_URL="${DEPLOY_URL}" ATTEMPTS="${DEPLOY_READINESS_ATTEMPTS}" SLEEP_SEC="${DEPLOY_READINESS_SLEEP_SEC}" CHECK_CAMERAS=1 \
    MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    ./scripts/verify-stack.sh --check-domain-health
fi
# 0.47 Health/readiness/status consistency gate (#530) — post-deploy: не блокировать fix readiness на prod.
if [[ ! "${BIRDLENSE_SKIP_HEALTH_READINESS_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  _hr_json="docs/reports/health_readiness_contract/health_readiness_contract_latest.json"
  _hr_md="docs/reports/health_readiness_contract/health_readiness_contract_latest.md"
  echo "  - Health Readiness Contract gate (post-deploy):"
  (cd "${REPO_ROOT}" && \
    MCP_TOKEN="${MCP_TOKEN:-}" \
    BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    python3 ./scripts/verify_health_readiness_contract.py \
      --base-url "${DEPLOY_URL}" \
      --out-json "${_hr_json}" \
      --out-md "${_hr_md}") || {
        echo "Ошибка: Health/Readiness Contract не пройден после деплоя."
        exit 1
      }
fi
# Post-deploy re-run: pre-deploy hub_unreachable → enforce real checks after health contract.
if [[ "${_ERROR_BUDGET_HUB_UNREACHABLE}" == "1" ]] && \
   [[ ! "${BIRDLENSE_SKIP_ERROR_BUDGET_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "  - Error Budget Gate (post-deploy, was hub_unreachable pre-deploy):"
  if ! (cd "${REPO_ROOT}" && \
    MCP_TOKEN="${MCP_TOKEN:-}" \
    BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON="${BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON:-}" \
    python3 ./scripts/error_budget_gate.py \
      --base-url "${DEPLOY_URL}" \
      --require-hub \
      --out-json "${_error_budget_json}" \
      --out-md "${_error_budget_md}"); then
    echo "Ошибка: Error Budget Gate не пройден после деплоя (hub доступен, проверки не ок)."
    exit 1
  fi
fi
if [[ "${_OWASP_HUB_UNREACHABLE}" == "1" ]] && \
   [[ ! "${BIRDLENSE_SKIP_OWASP_API_GATE:-}" =~ ^(1|true|yes)$ ]]; then
  echo "  - OWASP API Controls Gate (post-deploy, was hub_unreachable pre-deploy):"
  (cd "${REPO_ROOT}" && \
    MCP_TOKEN="${MCP_TOKEN:-}" \
    BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
    python3 ./scripts/verify_owasp_api_controls.py \
      --base-url "${DEPLOY_URL}" \
      --require-hub \
      --out-json "${_owasp_json}" \
      --out-md "${_owasp_md}") || {
        echo "Ошибка: OWASP API Controls gate не пройден после деплоя (hub доступен, проверки не ок)."
        exit 1
      }
fi
echo "  - Runtime SLI gate:"
BASE_URL="${DEPLOY_URL}" ATTEMPTS="${DEPLOY_READINESS_ATTEMPTS}" SLEEP_SEC="${DEPLOY_READINESS_SLEEP_SEC}" \
  MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
  MAX_HEARTBEAT_AGE_SECONDS="${MAX_HEARTBEAT_AGE_SECONDS:-240}" \
  MAX_HTTP_OVER_1000MS_RATIO="${MAX_HTTP_OVER_1000MS_RATIO:-0.20}" \
  MIN_HTTP_SAMPLE_COUNT="${MIN_HTTP_SAMPLE_COUNT:-20}" \
  ./scripts/check-runtime-sli.sh --base-url "${DEPLOY_URL}"
echo "  - Runtime performance gate:"
PERF_GATE_RETRIES="${PERF_GATE_RETRIES:-2}"
perf_gate_ok=0
for perf_attempt in $(seq 1 "${PERF_GATE_RETRIES}"); do
  if BASE_URL="${DEPLOY_URL}" \
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
      --out "${PERF_OUT:-/tmp/runtime_perf_gate.deploy.v1.json}"; then
    perf_gate_ok=1
    break
  fi
  if [[ "${perf_attempt}" -lt "${PERF_GATE_RETRIES}" ]]; then
    echo "  perf gate попытка ${perf_attempt}/${PERF_GATE_RETRIES} не прошла (часто сразу после bootstrap), повтор через 20 сек..."
    sleep 20
  fi
done
if [[ "${perf_gate_ok}" -eq 0 ]]; then
  echo "Ошибка: Runtime performance gate не пройден после ${PERF_GATE_RETRIES} попыток."
  exit 1
fi
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
# 3.1 Post-deploy detector config smoke (warn-only; see docs/contributor/hub-detector-runbook.md).
if [[ -f "${REPO_ROOT}/scripts/verify-prod-detector-smoke.sh" ]]; then
  echo "  - Detector config smoke (warn-only):"
  if ! (cd "${REPO_ROOT}" && chmod +x ./scripts/verify-prod-detector-smoke.sh && \
        ./scripts/verify-prod-detector-smoke.sh --no-yolo-smoke); then
    echo "  WARN: verify-prod-detector-smoke failed — check merged config (native_lores, Bird override, subtype=0)."
    echo "  Подсказка: make verify-prod-detector-smoke; docs/contributor/hub-detector-runbook.md"
  fi
fi
echo ""
echo "=== Готово. UI: ${DEPLOY_URL} ==="
echo "Записи и БД не трогаем; user_config.yaml не синхронизируем (есть бэкап .bak.deploy-* перед rsync)."
echo ""
echo "Если API недоступен из браузера: добавьте на сервере в app/.env:"
echo "  CORS_ORIGINS=${DEPLOY_URL}"
echo "(Сейчас без внешнего reverse proxy: тот же origin, что и UI — http://IP:порт; домен/HTTPS позже — обновите URL.)"
