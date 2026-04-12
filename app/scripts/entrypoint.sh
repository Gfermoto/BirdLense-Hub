#!/bin/bash
set -e
# Сброс прав на примонтированные тома, затем весь стек под birdlense (uid 1000), не root (#277).
if [ "$(id -u)" = "0" ]; then
  chown -R birdlense:birdlense /app/data /app/app_config 2>/dev/null || true
  exec gosu birdlense:birdlense /bin/bash "$0" "$@"
fi

# Go2RTC upstream: из GO2RTC_URL или video.go2rtc_url в конфиге
GO2RTC_UPSTREAM=$(python3 /app/scripts/get_go2rtc_upstream.py)
GO2RTC_UPSTREAM="${GO2RTC_UPSTREAM//[$'\r\n']/}"
BIRDLENSE_PORT="${BIRDLENSE_PORT:-8080}"
# Brotli: модуль из Dockerfile (ngx_brotli) или сторонний load_module
BROTLI_BLOCK=""
if [ -f /usr/lib/nginx/modules/ngx_http_brotli_filter_module.so ]; then
  BROTLI_BLOCK="  brotli on; brotli_comp_level 5; brotli_types application/json application/javascript text/css text/plain text/xml application/xml;"
fi
export BROTLI_BLOCK
python3 -c '
import os
t=open("/etc/nginx/conf.d/default.conf.template").read()
t=t.replace("__GO2RTC_UPSTREAM__", __import__("sys").argv[1])
t=t.replace("__BIRDLENSE_PORT__", __import__("sys").argv[2])
t=t.replace("__BROTLI_BLOCK__", os.environ.get("BROTLI_BLOCK", ""))
open("/etc/nginx/conf.d/default.conf","w").write(t)
' "$GO2RTC_UPSTREAM" "$BIRDLENSE_PORT"

# Образ не содержит записей/БД, но включает data/images — подмешиваем в примонтированный ./data
if [ -d /app/_bundled_data/images ]; then
  mkdir -p /app/data/images
  cp -a /app/_bundled_data/images/. /app/data/images/
fi
# Тестовый режим video.source=file: папка по умолчанию в volume ./data (см. video.file_dir)
mkdir -p /app/data/file_test

mkdir -p /tmp/nginx-client-body /tmp/nginx-proxy /tmp/nginx-fastcgi /tmp/nginx-uwsgi /tmp/nginx-scgi
nginx -c /app/nginx/docker-nginx-main.conf &
sleep 1
# gthread: несколько одновременных запросов к SQLite (WAL + check_same_thread=False в config)
GUNICORN_THREADS="${GUNICORN_THREADS:-16}"
cd /app/web && PYTHONPATH=/app gunicorn -w 1 -k gthread --threads "$GUNICORN_THREADS" --timeout 0 -b 127.0.0.1:8000 app:app &
# create_app() блокируется на отправке в Telegram (telegram_timeout может быть 300+ сек в РФ).
# Ждём до 400s, иначе контейнер выходит по таймауту и перезапускается → спам «App is UP!».
for i in $(seq 1 400); do curl -sf http://127.0.0.1:8000/api/ui/health >/dev/null && break; sleep 1; done
if ! curl -sf http://127.0.0.1:8000/api/ui/health >/dev/null; then
  echo "API health check failed after 400s (continuing anyway)"
  # Не выходим — контейнер остаётся живым для отладки; оркестратор может использовать healthcheck из compose
fi
# MCP server (при mcp.enabled) — HTTP на 8001, nginx проксирует /mcp
if python3 /app/scripts/check_mcp_enabled.py 2>/dev/null; then
  PYTHONPATH=/app python3 /app/web/birdlense_mcp.py --transport http --port 8001 --host 127.0.0.1 &
fi
# Процессор в цикле: при перезапуске по флагу из UI контейнер не выходит, перезапускается только процесс
while true; do
  # /app/web — импорт services.ebird_region_service для авто-порогов регионального топа (#128)
  PYTHONPATH=/app:/app/web python /app/processor/src/main.py || true
  echo "Processor exited, restarting in 2s..."
  sleep 2
done
