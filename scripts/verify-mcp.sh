#!/usr/bin/env bash
# Smoke-check MCP на развёрнутом хабе (нужен реальный MCP_TOKEN из app/.env на сервере).
# Использование:
#   export MCP_TOKEN='...'   # или: MCP_TOKEN=... ./scripts/verify-mcp.sh https://birdlense.example/
#   ./scripts/verify-mcp.sh https://birdlense.example/
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8085}"
BASE_URL="${BASE_URL%/}"
TOKEN="${MCP_TOKEN:-}"

if [[ -z "${TOKEN}" ]]; then
  echo "error: set MCP_TOKEN (same value as on the hub: MCP_TOKEN or mcp.token)" >&2
  exit 2
fi

body='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify-mcp.sh","version":"1.0"}}}'
tmp="$(mktemp)"
code="$(curl -sS -o "${tmp}" -w '%{http_code}' --max-time 20 \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -X POST "${BASE_URL}/mcp" \
  -d "${body}" || true)"

echo "POST ${BASE_URL}/mcp (initialize) -> HTTP ${code}"
head -c 500 "${tmp}" || true
echo
rm -f "${tmp}"

if [[ "${code}" != "200" ]]; then
  echo "error: expected HTTP 200 from initialize" >&2
  exit 1
fi
