#!/bin/bash
# Проверка стабильного релиза на сервере.
# Запуск: BASE_URL=http://192.168.1.11:8085 ./scripts/verify-release.sh
# С паролем: E2E_SETTINGS_PASSWORD=xxx BASE_URL=... ./scripts/verify-release.sh

set -euo pipefail
URL="${BASE_URL:-http://192.168.1.11:8085}"
REQUIRE_SETTINGS_HEALTH="${REQUIRE_SETTINGS_HEALTH:-0}"
TIMEOUT_SEC="${TIMEOUT_SEC:-20}"
AUTH_ARGS=()
if [ -n "${BIRDLENSE_UI_API_KEY:-}" ]; then
  AUTH_ARGS=(-H "X-Birdlense-Api-Key: ${BIRDLENSE_UI_API_KEY}")
fi

curl_json() {
  curl -sS --max-time "${TIMEOUT_SEC}" "${AUTH_ARGS[@]}" "$@"
}

show_or_fail_optional_json() {
  local label="$1"
  local path="$2"
  local tmp_file="$3"
  local code
  code=$(curl -sS --max-time "${TIMEOUT_SEC}" -o "${tmp_file}" -w "%{http_code}" "${AUTH_ARGS[@]}" "${URL}${path}")
  if [ "${code}" = "200" ]; then
    head -c 220 "${tmp_file}" && echo "..."
    return 0
  fi
  if [ "${code}" = "403" ]; then
    if [ "${REQUIRE_SETTINGS_HEALTH}" = "1" ]; then
      echo " FAIL (${label}: 403 locked, set BIRDLENSE_UI_API_KEY or open settings)"
      exit 1
    fi
    echo " SKIP (403 locked)"
    return 0
  fi
  echo " FAIL (${label}: HTTP ${code})"
  exit 1
}

echo "=== Проверка $URL ==="
echo ""

echo "1. Health:"
curl_json "$URL/api/ui/health" && echo " OK" || { echo " FAIL"; exit 1; }

echo "2. Status:"
curl_json "$URL/api/ui/status" | head -c 150 && echo "..."

echo ""
echo "3. Readiness:"
curl_json "$URL/api/ui/readiness" | head -c 150 && echo "..."

echo ""
echo "4. Path traversal (должен 403):"
code=$(curl -sI -o /dev/null -w "%{http_code}" --path-as-is "$URL/data/../.env")
if [ "$code" = "403" ]; then
  echo " OK (403)"
else
  echo " FAIL ($code)"
  exit 1
fi

echo ""
echo "5. Cameras:"
curl_json "$URL/api/ui/cameras" | head -c 100 && echo "..."

echo ""
echo "6. Domain health (если settings открыты):"
show_or_fail_optional_json "domain-health" "/api/ui/system/domain-health" "/tmp/birdlense-domain-health.json"

echo ""
echo "7. Species registry health (если settings открыты):"
show_or_fail_optional_json "species-registry-health" "/api/ui/system/species-registry/health" "/tmp/birdlense-registry-health.json"

echo ""
echo "8. Config audit (если settings открыты или strict auth разрешён):"
show_or_fail_optional_json "config-audit" "/api/ui/system/config-audit" "/tmp/birdlense-config-audit.json"

echo ""
echo "9. E2E тесты:"
cd "$(dirname "$0")/../app/e2e"
npm test 2>&1 | tail -5

echo ""
echo "=== Проверка завершена ==="
