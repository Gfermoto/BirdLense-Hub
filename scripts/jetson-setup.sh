#!/usr/bin/env bash
# BirdLense Hub — установка на Jetson Nano (L4T r32.7).
# Запуск на устройстве: sudo ./scripts/jetson-setup.sh
# Или с dev: DEPLOY_HOST=gfer@jetson ./scripts/jetson-setup.sh --remote
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE_DIR="$ROOT/deploy/profiles/jetson-nano"
SITE_ENV="${SITE_ENV:-$PROFILE_DIR/site.env}"
APP_DIR="$ROOT/app"
REMOTE=0

if ! python3 -c 'import yaml' 2>/dev/null; then
  echo "Installing PyYAML for config build (pip --user)..."
  python3 -m pip install --user --quiet pyyaml
fi
PYTHON=python3

usage() {
  cat <<'EOF'
Usage: jetson-setup.sh [options]

  --config-only     Только user_config + .env (без моделей и docker)
  --fetch-models    Скачать веса с Hugging Face
  --trt             Собрать TensorRT .engine (останавливает Hub)
  --build           docker compose build birdlense
  --up              docker compose up -d
  --verify          curl /api/ui/status
  --remote          Выполнить на DEPLOY_HOST через SSH (нужен deploy.local.sh)
  --bootstrap-torch torch/cpu fallback (без .engine)
  -h, --help

Без флагов: config → fetch-models (если нет pt) → build → up → verify.
Перед первым запуском: cp deploy/profiles/jetson-nano/site.example.env site.env и заполните.
EOF
}

DO_CONFIG=0
DO_FETCH=0
DO_TRT=0
DO_BUILD=0
DO_UP=0
DO_VERIFY=0
BOOTSTRAP_TORCH=0
RUN_ALL=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-only) RUN_ALL=0; DO_CONFIG=1 ;;
    --fetch-models) RUN_ALL=0; DO_FETCH=1 ;;
    --trt) RUN_ALL=0; DO_TRT=1 ;;
    --build) RUN_ALL=0; DO_BUILD=1 ;;
    --up) RUN_ALL=0; DO_UP=1 ;;
    --verify) RUN_ALL=0; DO_VERIFY=1 ;;
    --remote) REMOTE=1 ;;
    --bootstrap-torch) BOOTSTRAP_TORCH=1 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

if [[ "$RUN_ALL" == "1" ]]; then
  DO_CONFIG=1
  DO_FETCH=1
  DO_BUILD=1
  DO_UP=1
  DO_VERIFY=1
fi

_run() {
  if [[ "$REMOTE" == "1" ]]; then
    # shellcheck disable=SC1091
    set -a; [[ -f "$ROOT/scripts/deploy.local.sh" ]] && . "$ROOT/scripts/deploy.local.sh"; set +a
    : "${DEPLOY_HOST:?Set DEPLOY_HOST or scripts/deploy.local.sh}"
    local port="${DEPLOY_SSH_PORT:-22}"
    ssh -p "$port" "$DEPLOY_HOST" "cd '${DEPLOY_REMOTE_DIR:-/home/gfer/BirdLense}' && $*"
  else
    bash -c "$*"
  fi
}

_ensure_site_env() {
  if [[ ! -f "$SITE_ENV" ]]; then
    echo "ERROR: $SITE_ENV not found. Copy site.example.env → site.env and edit." >&2
    exit 2
  fi
}

_step_config() {
  echo "=== Config ==="
  _ensure_site_env
  local args=("$PYTHON" "$ROOT/scripts/build_jetson_user_config.py" --site-env "$SITE_ENV")
  [[ "$BOOTSTRAP_TORCH" == "1" ]] && args+=(--bootstrap-torch)
  _run "${args[*]}"
  if [[ ! -f "$APP_DIR/.env" ]]; then
    cp "$PROFILE_DIR/.env.example" "$APP_DIR/.env"
    echo "Created app/.env from .env.example — допишите секреты."
  fi
  # shellcheck disable=SC1090
  set -a; source "$SITE_ENV"; set +a
  grep -q '^FLASK_SECRET_KEY=' "$APP_DIR/.env" 2>/dev/null || {
    echo "FLASK_SECRET_KEY=$(openssl rand -hex 32)" >>"$APP_DIR/.env"
    echo "PROCESSOR_SECRET=$(openssl rand -hex 32)" >>"$APP_DIR/.env"
  }
  _sync_jetson_env
}

_sync_jetson_env() {
  # Не затираем секреты; обновляем только Jetson runtime keys из .env.example.
  if [[ "$BOOTSTRAP_TORCH" == "1" ]]; then
    local envf="$APP_DIR/.env"
    touch "$envf"
    for kv in \
      "BIRDLENSE_INFERENCE_BACKEND=torch" \
      "BIRDLENSE_INFERENCE_DEVICE=cpu" \
      "BIRDLENSE_CLASSIFIER_INFERENCE_BACKEND=torch" \
      "BIRDLENSE_OPENVINO_BINARY_ENABLED=0"; do
      key="${kv%%=*}"
      if grep -q "^${key}=" "$envf" 2>/dev/null; then
        sed -i "s|^${key}=.*|${kv}|" "$envf"
      else
        echo "$kv" >>"$envf"
      fi
    done
    return
  fi
  local example="$PROFILE_DIR/.env.example"
  [[ -f "$example" ]] || return
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^BIRDLENSE_ ]] || continue
    [[ "$line" =~ ^# ]] && continue
    local key="${line%%=*}"
    local val="${line#*=}"
    if grep -q "^${key}=" "$APP_DIR/.env" 2>/dev/null; then
      sed -i "s|^${key}=.*|${key}=${val}|" "$APP_DIR/.env"
    else
      echo "${key}=${val}" >>"$APP_DIR/.env"
    fi
  done <"$example"
  sed -i '/^BIRDLENSE_INFERENCE_DEVICE=/d' "$APP_DIR/.env" 2>/dev/null || true
}

_step_fetch() {
  echo "=== Fetch models ==="
  local trapper_pt="$APP_DIR/processor/models/detection/trapper_ai_v02_2024/trapper_ai_v02_2024.pt"
  if [[ "$REMOTE" == "1" ]]; then
    _run "test -f '$trapper_pt' || bash scripts/fetch_trapper_jetson.sh '$APP_DIR/processor/models/detection/trapper_ai_v02_2024' || true"
  else
    [[ -f "$trapper_pt" ]] || bash "$ROOT/scripts/fetch_trapper_jetson.sh" "$APP_DIR/processor/models/detection/trapper_ai_v02_2024"
  fi
  _run "bash scripts/fetch_chriamue_classifier.sh"
  _run "bash scripts/fetch_ornimetrics_jetson.sh"
  _run "JETSON_PRUNE_DRY_RUN=0 bash scripts/jetson_models_prune.sh app/processor/models"
}

_step_trt() {
  echo "=== TensorRT engine ==="
  _run "bash scripts/jetson_finish_trapper_trt.sh"
}

_step_build() {
  echo "=== Docker build ==="
  _run "cd app && docker compose -f docker-compose.yml -f docker-compose.jetson.yml build birdlense"
}

_step_up() {
  echo "=== Docker up ==="
  _run "cd app && docker compose -f docker-compose.yml -f docker-compose.jetson.yml up -d"
  _run "bash scripts/jetson-post-recreate-bootstrap.sh '$APP_DIR' || true"
}

_step_verify() {
  echo "=== Verify ==="
  local port="${BIRDLENSE_PORT:-8085}"
  _run "curl -sf 'http://127.0.0.1:${port}/api/ui/health' && curl -sf 'http://127.0.0.1:${port}/api/ui/status'"
  echo ""
  echo "OK — откройте UI (NAT: внешний порт → ${port} на устройстве)."
}

[[ "$DO_CONFIG" == "1" ]] && _step_config
[[ "$DO_FETCH" == "1" ]] && _step_fetch
[[ "$DO_TRT" == "1" ]] && _step_trt
[[ "$DO_BUILD" == "1" ]] && _step_build
[[ "$DO_UP" == "1" ]] && _step_up
[[ "$DO_VERIFY" == "1" ]] && _step_verify

echo "jetson-setup: done"
