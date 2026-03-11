#!/bin/bash
set -e
# Go2RTC upstream: из GO2RTC_URL или video.go2rtc_url в конфиге
GO2RTC_UPSTREAM=$(python3 /app/scripts/get_go2rtc_upstream.py)
python3 -c 'import sys; t=open("/etc/nginx/conf.d/default.conf.template").read(); t=t.replace("__GO2RTC_UPSTREAM__", sys.argv[1]); open("/etc/nginx/conf.d/default.conf","w").write(t)' "$GO2RTC_UPSTREAM"

nginx &
sleep 1
cd /app/web && PYTHONPATH=/app gunicorn -w 1 -b 127.0.0.1:8000 app:app &
for i in $(seq 1 30); do curl -sf http://127.0.0.1:8000/api/ui/health >/dev/null && break; sleep 1; done
if ! curl -sf http://127.0.0.1:8000/api/ui/health >/dev/null; then
  echo "API health check failed after 30s"
  exit 1
fi
# MCP server (при mcp.enabled) — HTTP на 8001, nginx проксирует /mcp
if python3 /app/scripts/check_mcp_enabled.py 2>/dev/null; then
  PYTHONPATH=/app python3 /app/web/birdlense_mcp.py --transport http --port 8001 --host 127.0.0.1 &
fi
PYTHONPATH=/app python /app/processor/src/main.py
