#!/bin/bash
set -e
#
# Single-container startup (order matters): Gunicorn -> HealthCheck -> Nginx
# Operability / «если зависло»:
#   docs/TROUBLESHOOTING.md → «Single-container startup (entrypoint)»
#   docs/RUNTIME_COUPLING.md — PYTHONPATH, web↔processor, compose dev-split draft
#

# =============================================================================
# SECTION 1 — Root bootstrap: volume ownership, DRM groups, drop to birdlense
# =============================================================================
if [ "$(id -u)" = "0" ]; then
  chown -R birdlense:birdlense /app/data /app/app_config 2>/dev/null || true
  if [ -d /dev/dri ]; then
    for dev in /dev/dri/renderD128 /dev/dri/card0; do
      [ -e "$dev" ] || continue
      gid="$(stat -c '%g' "$dev" 2>/dev/null || true)"
      [ -n "$gid" ] || continue
      [ "$gid" = "0" ] && continue
      if ! getent group "$gid" >/dev/null 2>&1; then
        groupadd -g "$gid" "hostgpu_$gid" 2>/dev/null || true
      fi
      grp="$(getent group "$gid" | awk -F: 'NR==1{print $1}')"
      [ -n "$grp" ] && usermod -aG "$grp" birdlense 2>/dev/null || true
    done
  fi
  exec gosu birdlense /bin/bash "$0" "$@"
fi

# =============================================================================
# SECTION 2 — Nginx config from template (Go2RTC upstream, listen port, Brotli)
# =============================================================================
GO2RTC_UPSTREAM=$(python3 /app/scripts/get_go2rtc_upstream.py)
GO2RTC_UPSTREAM="${GO2RTC_UPSTREAM//[$'\r\n']/}"
BIRDLENSE_PORT="${BIRDLENSE_PORT:-8080}"
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

# =============================================================================
# SECTION 3 — Data dirs: bundled catalog images, file-test path, nginx temp dirs
# =============================================================================
if [ -d /app/_bundled_data/images ]; then
  mkdir -p /app/data/images
  cp -a /app/_bundled_data/images/. /app/data/images/
fi
mkdir -p /app/data/file_test
mkdir -p /tmp/nginx-client-body /tmp/nginx-proxy /tmp/nginx-fastcgi /tmp/nginx-uwsgi /tmp/nginx-scgi

# =============================================================================
# SECTION 4 — Gunicorn (FastAPI on 127.0.0.1:8000)
# =============================================================================
GUNICORN_THREADS="${GUNICORN_THREADS:-16}"
cd /app/web && PYTHONPATH=/app gunicorn -w 1 -k gthread --threads "$GUNICORN_THREADS" --timeout 0 -b 127.0.0.1:8000 app:app &

# =============================================================================
# SECTION 5 — Wait for web liveness (/api/ui/health)
# =============================================================================
health_wait_left=400
until curl -sf http://127.0.0.1:8000/api/ui/health >/dev/null; do
  health_wait_left=$((health_wait_left - 1))
  [ "$health_wait_left" -le 0 ] && break
  sleep 1
done
if ! curl -sf http://127.0.0.1:8000/api/ui/health >/dev/null; then
  echo "WARNING: API health check failed after 400s (continuing anyway)"
fi

# =============================================================================
# SECTION 6 — Nginx (reverse proxy :8080 → gunicorn)
# =============================================================================
nginx -c /app/nginx/docker-nginx-main.conf &

# =============================================================================
# SECTION 7 — Optional MCP (127.0.0.1:8001)
# =============================================================================
if python3 /app/scripts/check_mcp_enabled.py 2>/dev/null; then
  PYTHONPATH=/app python3 /app/web/birdlense_mcp.py --transport streamable-http --port 8001 --host 127.0.0.1 &
fi

# =============================================================================
# SECTION 8 — Processor supervisor loop
# =============================================================================
while true; do
  PYTHONPATH=/app:/app/web python3 /app/processor/src/main.py || true
  echo "Processor exited, restarting in 2s..."
  sleep 2
done
