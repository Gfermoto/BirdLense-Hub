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
  # Jetson JP4.6: /dev/nvhost-* owned by group video — без неё torch.cuda недоступен py3.6 worker.
  if [ "${BIRDLENSE_PLATFORM:-}" = "jetson_nano" ] && getent group video >/dev/null 2>&1; then
    usermod -aG video birdlense 2>/dev/null || true
  fi
  # Jetson chriamue: model.onnx лежит в weights/ поддиректории
  chriamue_dir="/app/processor/models/classification/chriamue_bird_species_classifier"
  if [ -f "${chriamue_dir}/weights/model.onnx" ] && [ ! -f "${chriamue_dir}/model.onnx" ]; then
    ln -sf weights/model.onnx "${chriamue_dir}/model.onnx"
  fi
  # Make model dirs readable by birdlense user (bind-mounted from root)
  chmod -R a+rX /app/processor/models/ 2>/dev/null || true
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
  # Never clobber good volume files with empty/stale bundled assets (deploy excludes app/data).
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
if [ "${BIRDLENSE_PROCESSOR_ENABLED:-1}" = "0" ]; then
  echo "Processor loop disabled by BIRDLENSE_PROCESSOR_ENABLED=0"
  while true; do
    sleep 3600
  done
fi

# Jetson GPU worker (python3.6 + CUDA torch): TensorRT (.engine) или TorchScript (.torchscript).
# Supervised loop: respawns worker on crash with 2s delay.
if [ "${BIRDLENSE_PLATFORM:-}" = "jetson_nano" ] && \
   { [ "${BIRDLENSE_INFERENCE_BACKEND:-}" = "tensorrt" ] || [ "${BIRDLENSE_INFERENCE_BACKEND:-}" = "torch" ]; }; then
  if [ -x /usr/bin/python3.6 ] && [ -d /opt/jetson-cuda-py36 ]; then
    # Choose worker script based on backend
    _WORKER_SCRIPT="jetson_trt_worker.py"
    _WORKER_LABEL="TRT"
    if [ "${BIRDLENSE_INFERENCE_BACKEND:-}" = "torch" ]; then
      _WORKER_SCRIPT="jetson_torch_worker.py"
      _WORKER_LABEL="Torch"
    fi
    if ! pgrep -f "${_WORKER_SCRIPT}" >/dev/null 2>&1; then
      # Stale socket cleanup: remove old socket before starting worker
      rm -f /tmp/birdlense-trt.sock
      (
        _TRT_BACKOFF=2
        _TRT_BACKOFF_MAX=60
        _TRT_FAST_EXIT=30
        while true; do
          export PYTHONPATH="/opt/jetson-cuda-py36:/usr/lib/python3.6/dist-packages:/app/processor/src"
          export LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
          _trt_start=$(date +%s)
          /usr/bin/python3.6 /app/processor/src/inference/${_WORKER_SCRIPT}
          _trt_elapsed=$(( $(date +%s) - _trt_start ))
          echo "${_WORKER_LABEL} worker exited after ${_trt_elapsed}s, restarting in ${_TRT_BACKOFF}s..."
          # Exponential backoff for crash loops (e.g. OOM)
          if [ $_trt_elapsed -lt $_TRT_FAST_EXIT ]; then
            _TRT_BACKOFF=$(( _TRT_BACKOFF * 2 ))
            [ $_TRT_BACKOFF -gt $_TRT_BACKOFF_MAX ] && _TRT_BACKOFF=$_TRT_BACKOFF_MAX
          else
            _TRT_BACKOFF=2
          fi
          sleep $_TRT_BACKOFF
        done
      ) &
      echo "Started ${_WORKER_LABEL} worker (python3.6): ${_WORKER_SCRIPT}"
      _socket_sec=0
      for _i in $(seq 1 180); do
        [ -S /tmp/birdlense-trt.sock ] && { _socket_sec=$_i; break; }
        _socket_sec=$_i
        # Check worker is still alive every 5 seconds
        if [ $((_i % 5)) -eq 0 ]; then
          if ! pgrep -f "${_WORKER_SCRIPT}" >/dev/null 2>&1; then
            echo "WARNING: ${_WORKER_LABEL} worker process died during socket wait (attempt $_i/180)"
          fi
        fi
        sleep 1
      done
      if [ -S /tmp/birdlense-trt.sock ]; then
        echo "${_WORKER_LABEL} worker socket ready after ${_socket_sec}s"
      else
        echo "WARNING: ${_WORKER_LABEL} worker socket NOT ready after 180s — processor may fail to connect"
      fi
      unset _socket_sec _i _WORKER_SCRIPT _WORKER_LABEL
    fi
  fi
fi

# Processor supervisor: exponential backoff when processor dies quickly
_PROC_BACKOFF=2
_PROC_BACKOFF_MAX=30
_PROC_FAST_EXIT_THRESHOLD=15
while true; do
  PROC_PY="${JETSON_PROCESSOR_PYTHON:-}"
  if [ -z "$PROC_PY" ] && [ "${BIRDLENSE_PLATFORM:-}" = "jetson_nano" ]; then
    if [ -x /opt/conda/envs/birdlense/bin/python ]; then
      PROC_PY=/opt/conda/envs/birdlense/bin/python
    elif [ -d /opt/jetson-cuda-py36 ] && [ -x /usr/bin/python3.6 ]; then
      PROC_PY=/usr/bin/python3.6
    elif [ -x /opt/jetson-processor/bin/python ]; then
      PROC_PY=/opt/jetson-processor/bin/python
    fi
  fi
  if [ -z "$PROC_PY" ]; then
    PROC_PY=python3
  fi
  # TensorRT python bindings (JP4.6) + tegra libs для processor venv.
  if [ "${BIRDLENSE_PLATFORM:-}" = "jetson_nano" ]; then
    export LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
  fi
  _proc_start_ts=$(date +%s)
  PYTHONPATH=/app:/app/web:/app/processor/src "$PROC_PY" /app/processor/src/main.py || true
  _proc_elapsed=$(( $(date +%s) - _proc_start_ts ))
  echo "Processor exited after ${_proc_elapsed}s (exit code $?), restarting in ${_PROC_BACKOFF}s..."
  # Exponential backoff for crash loops
  if [ $_proc_elapsed -lt $_PROC_FAST_EXIT_THRESHOLD ]; then
    _PROC_BACKOFF=$(( _PROC_BACKOFF * 2 ))
    [ $_PROC_BACKOFF -gt $_PROC_BACKOFF_MAX ] && _PROC_BACKOFF=$_PROC_BACKOFF_MAX
  else
    _PROC_BACKOFF=2
  fi
  sleep $_PROC_BACKOFF
done
unset _PROC_BACKOFF _PROC_BACKOFF_MAX _PROC_FAST_EXIT_THRESHOLD _proc_start_ts _proc_elapsed
