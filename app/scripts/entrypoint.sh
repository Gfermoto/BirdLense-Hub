#!/bin/bash
set -e
#
# Single-container startup (order matters): Gunicorn -> HealthCheck -> Nginx
# Orin variant: ONNX GPU (CUDA EP / TensorRT EP). No DRM/DRI groups,
# no py3.6 worker (JetPack 6 has Python >=3.10 natively).
#

# =============================================================================
# SECTION 1 — Root bootstrap: volume ownership, drop to birdlense
# =============================================================================
if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data/.ultralytics
  if [ -L /app/app_config/app_config ]; then
    rm -f /app/app_config/app_config
  fi
  chown -R birdlense:birdlense /app/data /app/app_config 2>/dev/null || true
  chmod -R a+rX /app/processor/models/ 2>/dev/null || true
  exec gosu birdlense /bin/bash "$0" "$@"
fi

# Orin: nvidia pip wheels (cublas/cudnn) must be on LD_LIBRARY_PATH for ONNX Runtime CUDA EP.
if [ "${BIRDLENSE_PLATFORM:-orin}" = "orin" ]; then
  _py_site="/usr/local/lib/python3.12/site-packages"
  _ort_ld=""
  for _d in "${_py_site}/nvidia/cu13/lib" "${_py_site}/nvidia/cudnn/lib"; do
    if [ -d "$_d" ]; then
      _ort_ld="${_ort_ld:+${_ort_ld}:}${_d}"
    fi
  done
  if [ -n "$_ort_ld" ]; then
    export LD_LIBRARY_PATH="${_ort_ld}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  fi
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
  while IFS= read -r -d '' _bundled_src; do
    _rel="${_bundled_src#/app/_bundled_data/images/}"
    _dest="/app/data/images/${_rel}"
    mkdir -p "$(dirname "$_dest")"
    _src_size="$(stat -c '%s' "$_bundled_src" 2>/dev/null || echo 0)"
    [ "$_src_size" -gt 0 ] || continue
    if [ ! -f "$_dest" ]; then
      cp -a "$_bundled_src" "$_dest"
      continue
    fi
    _dest_size="$(stat -c '%s' "$_dest" 2>/dev/null || echo 0)"
    if [ "$_dest_size" -eq 0 ] || [ "$_src_size" -gt "$_dest_size" ]; then
      cp -a "$_bundled_src" "$_dest"
    fi
  done < <(find /app/_bundled_data/images -type f -print0)
fi
mkdir -p /app/data/file_test
mkdir -p /tmp/nginx-client-body /tmp/nginx-proxy /tmp/nginx-fastcgi /tmp/nginx-uwsgi /tmp/nginx-scgi

# =============================================================================
# SECTION 4 — Gunicorn (FastAPI on 127.0.0.1:8000)
# =============================================================================
GUNICORN_THREADS="${GUNICORN_THREADS:-16}"
cd /app/web && PYTHONPATH=/app:/app/web:/app/processor/src gunicorn -w 1 -k gthread --threads "$GUNICORN_THREADS" --timeout 0 -b 127.0.0.1:8000 app:app &

# =============================================================================
# SECTION 4b — Nginx before API ready (port :8080 responds immediately, 502 if upstream not ready)
# =============================================================================
nginx -c /app/nginx/docker-nginx-main.conf &

# =============================================================================
# SECTION 5 — Wait for web liveness (/api/ui/health)
# =============================================================================
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
if [ "${BIRDLENSE_PROCESSOR_ENABLED:-1}" = "0" ]; then
  echo "Processor loop disabled by BIRDLENSE_PROCESSOR_ENABLED=0"
  while true; do
    sleep 3600
  done
fi

# Orin: no separate GPU worker needed. ONNX Runtime uses CUDA EP / TensorRT EP directly.
# Processor runs in the main Python process with ONNX GPU.
_PROC_BACKOFF=2
_PROC_BACKOFF_MAX=30
_PROC_FAST_EXIT_THRESHOLD=15
while true; do
  _proc_start_ts=$(date +%s)
  PYTHONPATH=/app:/app/web:/app/processor/src python3 /app/processor/src/main.py || true
  _proc_elapsed=$(( $(date +%s) - _proc_start_ts ))
  echo "Processor exited after ${_proc_elapsed}s (exit code $?), restarting in ${_PROC_BACKOFF}s..."
  if [ $_proc_elapsed -lt $_PROC_FAST_EXIT_THRESHOLD ]; then
    _PROC_BACKOFF=$(( _PROC_BACKOFF * 2 ))
    [ $_PROC_BACKOFF -gt $_PROC_BACKOFF_MAX ] && _PROC_BACKOFF=$_PROC_BACKOFF_MAX
  else
    _PROC_BACKOFF=2
  fi
  sleep $_PROC_BACKOFF
done
unset _PROC_BACKOFF _PROC_BACKOFF_MAX _PROC_FAST_EXIT_THRESHOLD _proc_start_ts _proc_elapsed
