#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8085}"
ATTEMPTS="${ATTEMPTS:-30}"
SLEEP_SEC="${SLEEP_SEC:-2}"
TIMEOUT_SEC="${TIMEOUT_SEC:-15}"
CHECK_CAMERAS="${CHECK_CAMERAS:-0}"
CHECK_DOMAIN_HEALTH="${CHECK_DOMAIN_HEALTH:-0}"
STRICT_QUALITY="${STRICT_QUALITY:-0}"
UI_API_KEY="${BIRDLENSE_UI_API_KEY:-${UI_API_KEY:-}}"
MCP_TOKEN="${MCP_TOKEN:-}"

usage() {
  cat <<'EOF'
Usage: scripts/verify-stack.sh [--base-url URL] [--attempts N] [--sleep SEC] [--check-cameras] [--check-domain-health] [--strict-quality]

Verifies the shared install/deploy contract:
1. /api/ui/health responds with {"status":"ok"}
2. /api/ui/readiness responds with {"ready":true}
3. /api/ui/status reports web=ok (на strict production — с MCP_TOKEN или BIRDLENSE_UI_API_KEY)

Optional:
  --check-cameras   Also fetch /api/ui/cameras and print a short preview (те же заголовки, если заданы).
  --check-domain-health   Also require domain-health, species-registry health, and config-audit.
                            On strict hubs set BIRDLENSE_UI_API_KEY (or UI_API_KEY) for
                            X-Birdlense-Api-Key, or MCP_TOKEN for Authorization: Bearer (same as MCP);
                            otherwise those endpoints may 403.
  --strict-quality       Requires --check-domain-health and fails if strict_quality_ready is false.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --attempts)
      ATTEMPTS="$2"
      shift 2
      ;;
    --sleep)
      SLEEP_SEC="$2"
      shift 2
      ;;
    --check-cameras)
      CHECK_CAMERAS=1
      shift
      ;;
    --check-domain-health)
      CHECK_DOMAIN_HEALTH=1
      shift
      ;;
    --strict-quality)
      STRICT_QUALITY=1
      CHECK_DOMAIN_HEALTH=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

normalize_json() {
  tr -d '\n\r\t '
}

json_path_present() {
  local path="$1"
  python3 -c '
import json
import sys
path = [p for p in (sys.argv[1] or "").split(".") if p]
try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    sys.exit(2)
cur = data
for token in path:
    if not isinstance(cur, dict) or token not in cur:
        sys.exit(1)
    cur = cur[token]
sys.exit(0)
' "$path"
}

json_path_is_true() {
  local path="$1"
  python3 -c '
import json
import sys
path = [p for p in (sys.argv[1] or "").split(".") if p]
try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    sys.exit(2)
cur = data
for token in path:
    if not isinstance(cur, dict) or token not in cur:
        sys.exit(1)
    cur = cur[token]
sys.exit(0 if cur is True else 1)
' "$path"
}

fetch_with_retries() {
  local path="$1"
  local body=""
  local attempt
  for attempt in $(seq 1 "${ATTEMPTS}"); do
    if body="$(curl -sS -L --max-time "${TIMEOUT_SEC}" "${BASE_URL}${path}")"; then
      printf '%s' "${body}"
      return 0
    fi
    if [[ "${attempt}" -lt "${ATTEMPTS}" ]]; then
      sleep "${SLEEP_SEC}"
    fi
  done
  return 1
}

fetch_with_retries_auth() {
  local path="$1"
  local body=""
  local attempt
  local curl_args=()
  if [[ -n "${UI_API_KEY}" ]]; then
    curl_args=(-H "X-Birdlense-Api-Key: ${UI_API_KEY}")
  elif [[ -n "${MCP_TOKEN}" ]]; then
    curl_args=(-H "Authorization: Bearer ${MCP_TOKEN}")
  fi
  for attempt in $(seq 1 "${ATTEMPTS}"); do
    if body="$(curl -sS -L --max-time "${TIMEOUT_SEC}" "${curl_args[@]}" "${BASE_URL}${path}")"; then
      printf '%s' "${body}"
      return 0
    fi
    if [[ "${attempt}" -lt "${ATTEMPTS}" ]]; then
      sleep "${SLEEP_SEC}"
    fi
  done
  return 1
}

echo "verify-stack: base=${BASE_URL}"

health_body="$(fetch_with_retries '/api/ui/health')" || {
  echo "health: FAIL (${BASE_URL}/api/ui/health unreachable)" >&2
  exit 1
}
if ! printf '%s' "${health_body}" | python3 -c '
import json
import sys
try:
    payload = json.loads(sys.stdin.read() or "{}")
except Exception:
    sys.exit(1)
sys.exit(0 if payload.get("status") == "ok" else 1)
'
then
  echo "health: FAIL ${health_body}" >&2
  exit 1
fi
echo "health: OK ${health_body}"

readiness_body=""
readiness_attempt=""
for readiness_attempt in $(seq 1 "${ATTEMPTS}"); do
  if readiness_body="$(curl -sS -L --max-time "${TIMEOUT_SEC}" "${BASE_URL}/api/ui/readiness" 2>/dev/null)" \
    && printf '%s' "${readiness_body}" | json_path_is_true "ready"; then
    break
  fi
  if [[ "${readiness_attempt}" -lt "${ATTEMPTS}" ]]; then
    echo "readiness: waiting for processor bootstrap (${readiness_attempt}/${ATTEMPTS}, sleep ${SLEEP_SEC}s)..." >&2
    sleep "${SLEEP_SEC}"
    readiness_body=""
  fi
done
if [[ -z "${readiness_body}" ]] || ! printf '%s' "${readiness_body}" | json_path_is_true "ready"; then
  echo "readiness: FAIL ${readiness_body:-unreachable after ${ATTEMPTS} attempts}" >&2
  exit 1
fi
echo "readiness: OK ${readiness_body}"

# /api/ui/status не в strict allowlist — без сессии нужен MCP Bearer или UI API key
if [[ -n "${UI_API_KEY}" ]] || [[ -n "${MCP_TOKEN}" ]]; then
  if [[ -n "${UI_API_KEY}" ]]; then
    echo "verify-stack: status auth=BIRDLENSE_UI_API_KEY (X-Birdlense-Api-Key)"
  else
    echo "verify-stack: status auth=MCP_TOKEN (Authorization: Bearer)"
  fi
  status_body="$(fetch_with_retries_auth '/api/ui/status')" || {
    echo "status: FAIL (${BASE_URL}/api/ui/status unreachable)" >&2
    exit 1
  }
else
  status_body="$(fetch_with_retries '/api/ui/status')" || {
    echo "status: FAIL (${BASE_URL}/api/ui/status unreachable)" >&2
    exit 1
  }
fi
if ! printf '%s' "${status_body}" | python3 -c '
import json
import sys
try:
    payload = json.loads(sys.stdin.read() or "{}")
except Exception:
    sys.exit(1)
sys.exit(0 if payload.get("web") == "ok" else 1)
'
then
  echo "status: FAIL ${status_body}" >&2
  exit 1
fi
echo "status: OK ${status_body}"

if [[ "${CHECK_CAMERAS}" == "1" ]]; then
  cam_auth=()
  if [[ -n "${UI_API_KEY}" ]]; then
    cam_auth=(-H "X-Birdlense-Api-Key: ${UI_API_KEY}")
  elif [[ -n "${MCP_TOKEN}" ]]; then
    cam_auth=(-H "Authorization: Bearer ${MCP_TOKEN}")
  fi
  if cameras_body="$(curl -sS -L --max-time "${TIMEOUT_SEC}" "${cam_auth[@]}" "${BASE_URL}/api/ui/cameras" 2>/dev/null)"; then
    preview="$(printf '%s' "${cameras_body}" | head -c 200)"
    echo "cameras: INFO ${preview}..."
  else
    echo "cameras: WARN not reachable"
  fi
fi

if [[ "${CHECK_DOMAIN_HEALTH}" == "1" ]]; then
  if [[ -n "${UI_API_KEY}" ]]; then
    echo "verify-stack: domain-health auth=BIRDLENSE_UI_API_KEY (X-Birdlense-Api-Key)"
  elif [[ -n "${MCP_TOKEN}" ]]; then
    echo "verify-stack: domain-health auth=MCP_TOKEN (Authorization: Bearer)"
  else
    echo "verify-stack: WARN --check-domain-health without BIRDLENSE_UI_API_KEY or MCP_TOKEN (may 403)" >&2
  fi
  domain_body="$(fetch_with_retries_auth '/api/ui/system/domain-health')" || {
    echo "domain-health: FAIL (${BASE_URL}/api/ui/system/domain-health unreachable)" >&2
    exit 1
  }
  if ! printf '%s' "${domain_body}" | json_path_present "domain_contract_version"; then
    if [[ "${STRICT_QUALITY}" != "1" ]] && [[ -z "${UI_API_KEY}" ]] && [[ -z "${MCP_TOKEN}" ]] \
      && printf '%s' "${domain_body}" | grep -qi 'authentication'; then
      echo "domain-health: SKIP (strict hub requires BIRDLENSE_UI_API_KEY or MCP_TOKEN; health/readiness already OK)" >&2
      echo "verify-stack: PASS"
      exit 0
    fi
    echo "domain-health: FAIL ${domain_body}" >&2
    exit 1
  fi
  if [[ "${STRICT_QUALITY}" == "1" ]]; then
    if ! printf '%s' "${domain_body}" | json_path_is_true "strict_quality.strict_quality_ready"; then
      echo "domain-health: FAIL strict quality gate ${domain_body}" >&2
      exit 1
    fi
  fi
  echo "domain-health: OK $(printf '%s' "${domain_body}" | head -c 220)..."

  registry_body="$(fetch_with_retries_auth '/api/ui/system/species-registry/health')" || {
    echo "species-registry-health: FAIL (${BASE_URL}/api/ui/system/species-registry/health unreachable)" >&2
    exit 1
  }
  # Health payload is metrics-only (no top-level ok); require core counters.
  if ! printf '%s' "${registry_body}" | json_path_present "species_total"; then
    echo "species-registry-health: FAIL (missing species_total) ${registry_body}" >&2
    exit 1
  fi
  if ! printf '%s' "${registry_body}" | json_path_is_true "drift_scan_complete"; then
    echo "species-registry-health: FAIL partial drift scan ${registry_body}" >&2
    exit 1
  fi
  echo "species-registry-health: OK $(printf '%s' "${registry_body}" | head -c 220)..."

  config_body="$(fetch_with_retries_auth '/api/ui/system/config-audit')" || {
    echo "config-audit: FAIL (${BASE_URL}/api/ui/system/config-audit unreachable)" >&2
    exit 1
  }
  if ! printf '%s' "${config_body}" | json_path_present "config_warnings"; then
    echo "config-audit: FAIL (missing config_warnings) ${config_body}" >&2
    exit 1
  fi
  echo "config-audit: OK $(printf '%s' "${config_body}" | head -c 220)..."
fi

echo "verify-stack: PASS"
