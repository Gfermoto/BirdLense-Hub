#!/usr/bin/env bash
# Ожидание готовности Hub по HTTP (через Nginx на хосте).
# В entrypoint Nginx стартует только после health Gunicorn (до ~400 с) — цикл должен быть длиннее 120 с CI.
set -euo pipefail
BASE="${1:?usage: wait-hub-http.sh BASE_URL [max_attempts]}"
MAX="${2:-240}"
for i in $(seq 1 "$MAX"); do
  if curl -sf --connect-timeout 5 --max-time 20 --retry 2 "${BASE}/api/ui/health" >/dev/null; then
    echo "hub healthy (${i}/${MAX})"
    exit 0
  fi
  sleep 2
done
echo "hub not healthy after $((MAX * 2))s: ${BASE}/api/ui/health" >&2
exit 1
