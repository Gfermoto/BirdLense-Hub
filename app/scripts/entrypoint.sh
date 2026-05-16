#!/bin/bash
set -e
#
# Single-container startup (order matters): Gunicorn -> HealthCheck -> Nginx
# Operability / «если зависло»:
#   docs/user/troubleshooting.md → «Single-container startup (entrypoint)»
#   archive/internal/docs-legacy/RUNTIME_COUPLING.md — PYTHONPATH, web↔processor, compose dev-split draft
#

# =============================================================================
# SECTION 1 — Root bootstrap: volume ownership, DRM groups, drop to birdlense
# =============================================================================
if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data/.ultralytics
  # Битый symlink app_config/app_config -> /app/app_config ломает import app_config.app_config
  # (Python берёт каталог вместо app_config.py). Удаляем только если это symlink.
  if [ -L /app/app_config/app_config ]; then
    rm -f /app/app_config/app_config
  fi
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
truthy = {"1", "true", "yes", "on"}
raw_hide = os.environ.get("BIRDLENSE_HIDE_DIRECT_RECORDINGS", "").strip().lower()
if raw_hide:
    hide = raw_hide in truthy
else:
    env_name = os.environ.get("BIRDLENSE_ENV", "").strip().lower()
    strict_auth = os.environ.get("BIRDLENSE_STRICT_API_AUTH", "").strip().lower() in truthy
    # Safer default for public deployments: hide direct static recordings URLs
    # whenever strict production auth is enabled.
    hide = env_name == "production" and strict_auth
recordings_block = (
    ""
    if hide
    else """  location ^~ /data/recordings/ {
    alias /app/data/recordings/;
    autoindex off;
    add_header Accept-Ranges bytes;
  }
"""
)
t = open("/etc/nginx/conf.d/default.conf.template").read()
t = t.replace("__GO2RTC_UPSTREAM__", __import__("sys").argv[1])
t = t.replace("__BIRDLENSE_PORT__", __import__("sys").argv[2])
t = t.replace("__BROTLI_BLOCK__", os.environ.get("BROTLI_BLOCK", ""))
t = t.replace("__RECORDINGS_LOCATION_BLOCK__", recordings_block)
open("/etc/nginx/conf.d/default.conf", "w").write(t)
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
# processor/src — пакет inference (ml_lineage_service, processor_*); см. archive/internal/docs-legacy/RUNTIME_COUPLING.md
cd /app/web && PYTHONPATH=/app:/app/web:/app/processor/src gunicorn -w 1 -k gthread --threads "$GUNICORN_THREADS" --timeout 0 -b 127.0.0.1:8000 app:app &

# =============================================================================
# SECTION 4b — Nginx раньше ожидания API (порт :8080 сразу на хосте; до готовности upstream — 502, не «молча»)
# =============================================================================
# Иначе CI/прокси ждут до 400 с без ответа на :8085 → curl 56. См. scripts/wait-hub-http.sh, .github/workflows/ci-pr.yml.
nginx -c /app/nginx/docker-nginx-main.conf &

# =============================================================================
# SECTION 5 — Wait for web liveness (/api/ui/health)
# =============================================================================
# даём Gunicorn время привязаться к порту перед проверкой
sleep 5
health_wait_left=400
until curl -sf --max-time 120 http://127.0.0.1:8000/api/ui/health >/dev/null; do
  health_wait_left=$((health_wait_left - 1))
  [ "$health_wait_left" -le 0 ] && break
  sleep 1
done
if ! curl -sf --max-time 120 http://127.0.0.1:8000/api/ui/health >/dev/null; then
  echo "WARNING: API health check failed after 400s (continuing anyway)"
fi

# =============================================================================
# SECTION 7 — Optional MCP (127.0.0.1:8001)
# =============================================================================
if python3 /app/scripts/check_mcp_enabled.py 2>/dev/null; then
  PYTHONPATH=/app python3 /app/web/birdlense_mcp.py --transport streamable-http --port 8001 --host 127.0.0.1 &
fi

# =============================================================================
# SECTION 8 — Optional daily Re-ID SSL scheduler (inside container only)
# =============================================================================
is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

if is_true "${BIRDLENSE_REID_SSL_DAILY_ENABLED:-0}"; then
  REID_SSL_DB="${BIRDLENSE_REID_SSL_DB:-/app/data/db/birdlense.db}"
  REID_SSL_WINDOW_HOURS="${BIRDLENSE_REID_SSL_WINDOW_HOURS:-24}"
  REID_SSL_LIMIT="${BIRDLENSE_REID_SSL_LIMIT:-400}"
  REID_SSL_CLUSTER_THRESHOLD="${BIRDLENSE_REID_SSL_CLUSTER_THRESHOLD:-0.88}"
  REID_SSL_REPORT_JSON="${BIRDLENSE_REID_SSL_REPORT_JSON:-/app/data/reid_ssl_reports/latest.json}"
  REID_SSL_INTERVAL_SEC="${BIRDLENSE_REID_SSL_INTERVAL_SEC:-86400}"
  REID_SSL_START_DELAY_SEC="${BIRDLENSE_REID_SSL_START_DELAY_SEC:-300}"

  run_reid_ssl_cycle_once() {
    cmd=(
      python3 /app/scripts/reid/run_daily_ssl_cycle.py
      --db "${REID_SSL_DB}"
      --window-hours "${REID_SSL_WINDOW_HOURS}"
      --limit "${REID_SSL_LIMIT}"
      --cluster-threshold "${REID_SSL_CLUSTER_THRESHOLD}"
      --report-json "${REID_SSL_REPORT_JSON}"
    )
    if is_true "${BIRDLENSE_REID_SSL_UPDATE_VIDEO_NICKNAMES:-1}"; then
      cmd+=(--update-video-nicknames)
    fi
    echo "[reid-ssl] start: ${cmd[*]}"
    if command -v flock >/dev/null 2>&1; then
      flock -n /tmp/birdlense-reid-ssl.lock "${cmd[@]}" || true
    else
      "${cmd[@]}" || true
    fi
    echo "[reid-ssl] done"
  }

  (
    sleep "${REID_SSL_START_DELAY_SEC}"
    while true; do
      run_reid_ssl_cycle_once
      sleep "${REID_SSL_INTERVAL_SEC}"
    done
  ) &
  echo "[reid-ssl] scheduler enabled (interval=${REID_SSL_INTERVAL_SEC}s, start_delay=${REID_SSL_START_DELAY_SEC}s)"
fi

# =============================================================================
# SECTION 9 — Processor supervisor loop
# =============================================================================
while true; do
  PYTHONPATH=/app:/app/web python3 /app/processor/src/main.py || true
  echo "Processor exited, restarting in 2s..."
  sleep 2
done
