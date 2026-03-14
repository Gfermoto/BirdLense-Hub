#!/bin/bash
# Проверка стабильного релиза на сервере.
# Запуск: BASE_URL=http://192.168.1.11:8085 ./scripts/verify-release.sh
# С паролем: E2E_SETTINGS_PASSWORD=xxx BASE_URL=... ./scripts/verify-release.sh

set -e
URL="${BASE_URL:-http://192.168.1.11:8085}"

echo "=== Проверка $URL ==="
echo ""

echo "1. Health:"
curl -sf "$URL/api/ui/health" && echo " OK" || { echo " FAIL"; exit 1; }

echo "2. Status:"
curl -sf "$URL/api/ui/status" | head -c 150 && echo "..."

echo ""
echo "3. Path traversal (должен 403):"
code=$(curl -sI -o /dev/null -w "%{http_code}" --path-as-is "$URL/data/../.env")
[ "$code" = "403" ] && echo " OK (403)" || echo " FAIL ($code)"

echo ""
echo "4. Cameras:"
curl -sf "$URL/api/ui/cameras" | head -c 100 && echo "..."

echo ""
echo "5. E2E тесты:"
cd "$(dirname "$0")/../app/e2e" && npm test 2>&1 | tail -5

echo ""
echo "=== Проверка завершена ==="
