#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8085}"
ATTEMPTS="${ATTEMPTS:-30}"
SLEEP_SEC="${SLEEP_SEC:-2}"
TIMEOUT_SEC="${TIMEOUT_SEC:-15}"
CHECK_CAMERAS="${CHECK_CAMERAS:-0}"

usage() {
  cat <<'EOF'
Usage: scripts/verify-stack.sh [--base-url URL] [--attempts N] [--sleep SEC] [--check-cameras]

Verifies the shared install/deploy contract:
1. /api/ui/health responds with {"status":"ok"}
2. /api/ui/readiness responds with {"ready":true}
3. /api/ui/status reports web=ok

Optional:
  --check-cameras   Also fetch /api/ui/cameras and print a short preview.
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

echo "verify-stack: base=${BASE_URL}"

health_body="$(fetch_with_retries '/api/ui/health')" || {
  echo "health: FAIL (${BASE_URL}/api/ui/health unreachable)" >&2
  exit 1
}
if ! printf '%s' "${health_body}" | normalize_json | grep -q '"status":"ok"'; then
  echo "health: FAIL ${health_body}" >&2
  exit 1
fi
echo "health: OK ${health_body}"

readiness_body="$(fetch_with_retries '/api/ui/readiness')" || {
  echo "readiness: FAIL (${BASE_URL}/api/ui/readiness unreachable)" >&2
  exit 1
}
if ! printf '%s' "${readiness_body}" | normalize_json | grep -q '"ready":true'; then
  echo "readiness: FAIL ${readiness_body}" >&2
  exit 1
fi
echo "readiness: OK ${readiness_body}"

status_body="$(fetch_with_retries '/api/ui/status')" || {
  echo "status: FAIL (${BASE_URL}/api/ui/status unreachable)" >&2
  exit 1
}
if ! printf '%s' "${status_body}" | normalize_json | grep -q '"web":"ok"'; then
  echo "status: FAIL ${status_body}" >&2
  exit 1
fi
echo "status: OK ${status_body}"

if [[ "${CHECK_CAMERAS}" == "1" ]]; then
  if cameras_body="$(curl -sS -L --max-time "${TIMEOUT_SEC}" "${BASE_URL}/api/ui/cameras" 2>/dev/null)"; then
    preview="$(printf '%s' "${cameras_body}" | head -c 200)"
    echo "cameras: INFO ${preview}..."
  else
    echo "cameras: WARN not reachable"
  fi
fi

echo "verify-stack: PASS"
