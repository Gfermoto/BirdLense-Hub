#!/usr/bin/env bash
# Полностью автономный прод-деплой TrapperAI v02.2024 @704 (zero-touch).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST}"
REMOTE="${DEPLOY_REMOTE_DIR}"
PORT="${DEPLOY_SSH_PORT:-22}"
SSH_OPTS="-p ${PORT} -o ServerAliveInterval=30 -o ServerAliveCountMax=60"
RSYNC_SSH="ssh ${SSH_OPTS}"
W="${REPO_ROOT}/app/processor/models/detection/weights"
OV_LOCAL="${W}/trapper_ai_v02_2024_openvino_model"
PT_LOCAL="${W}/trapper_ai_v02_2024.pt"
REPORT="${REPO_ROOT}/docs/reports/fully_autonomous_deploy_report.md"
LOG="${REPO_ROOT}/docs/reports/fully_autonomous_deploy.log"
mkdir -p "$(dirname "${REPORT}")"
: > "${LOG}"

log() { echo "[$(date -Iseconds)] $*" | tee -a "${LOG}"; }

fail() {
  log "FAIL: $*"
  exit 1
}

# --- ЭТАП 1: артефакты ---
log "STAGE 1: verify local weights @704"
bash "${SCRIPT_DIR}/sync_trapper_weights.sh" --check >>"${LOG}" 2>&1 || fail "local trapper weights check"

log "STAGE 1: local docker smoke (CPU)"
cd "${REPO_ROOT}/app"
docker compose run --rm -T -v "${REPO_ROOT}:/repo:ro" birdlense \
  python3 /repo/scripts/trapper_ov_smoke_test.py --imgsz 704 --conf 0.25 \
  >>"${LOG}" 2>&1 || fail "local smoke"
cd "${REPO_ROOT}"

log "STAGE 1: rsync deploy scripts → VPS"
rsync -az -e "${RSYNC_SSH}" \
  "${SCRIPT_DIR}/sync_trapper_weights.sh" \
  "${SCRIPT_DIR}/trapper_ov_smoke_test.py" \
  "${SCRIPT_DIR}/patch_prod_trapper_user_config.py" \
  "${SCRIPT_DIR}/fully_autonomous_trapper_deploy.sh" \
  "${HOST}:${REMOTE}/scripts/" >>"${LOG}" 2>&1

log "STAGE 1: rsync weights → VPS"
bash "${SCRIPT_DIR}/sync_trapper_weights.sh" --check --rsync-vps >>"${LOG}" 2>&1 || fail "rsync trapper weights"

log "STAGE 1: sha256 local vs VPS"
LOCAL_SHA="$(sha256sum "${OV_LOCAL}/best.bin" "${OV_LOCAL}/metadata.yaml" "${PT_LOCAL}" | awk '{print $1}' | paste -sd, -)"
REMOTE_SHA="$(ssh ${SSH_OPTS} "${HOST}" "sha256sum ${REMOTE}/app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/best.bin ${REMOTE}/app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/metadata.yaml ${REMOTE}/app/processor/models/detection/weights/trapper_ai_v02_2024.pt | awk '{print \$1}' | paste -sd, -")"
[[ "${LOCAL_SHA}" == "${REMOTE_SHA}" ]] || fail "sha256 mismatch local=${LOCAL_SHA} remote=${REMOTE_SHA}"
log "sha256 OK"

log "STAGE 1: cleanup stray IR files in weights root on VPS"
ssh ${SSH_OPTS} "${HOST}" "cd ${REMOTE}/app/processor/models/detection/weights && rm -f best.bin best.xml metadata.yaml export_report.json trapper_ai_v02_2024.bin trapper_ai_v02_2024.xml 2>/dev/null || true"

log "STAGE 1: VPS docker smoke (intel GPU)"
ssh ${SSH_OPTS} "${HOST}" "cd ${REMOTE}/app && docker compose -f docker-compose.yml -f docker-compose.override.yml run --rm -T \
  -v ${REMOTE}:/repo:ro birdlense \
  python3 /repo/scripts/trapper_ov_smoke_test.py --ov-dir /app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model \
  --device intel:gpu --imgsz 704 --conf 0.25" >>"${LOG}" 2>&1 || fail "VPS smoke GPU"

# --- ЭТАП 2: код + конфиг ---
log "STAGE 2: rsync code (deploy subset)"
RSYNC_EXCLUDES="--exclude=.git --exclude=node_modules --exclude=__pycache__ --exclude=.env"
RSYNC_EXCLUDES="${RSYNC_EXCLUDES} --exclude=datasets --exclude=app/data --exclude=app/.env"
RSYNC_EXCLUDES="${RSYNC_EXCLUDES} --exclude=app/app_config/user_config.yaml --exclude=scripts/deploy.local.sh"
RSYNC_EXCLUDES="${RSYNC_EXCLUDES} --exclude=.venv --exclude=app/.venv --exclude=site"
RSYNC_EXCLUDES="${RSYNC_EXCLUDES} --exclude=app/.ruff_cache --exclude=app/.pytest_cache --exclude=.tools"
rsync -az --delete -e "${RSYNC_SSH}" ${RSYNC_EXCLUDES} \
  --filter "P app/processor/models/detection/weights/*.pt" \
  --filter "P app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/" \
  --filter "P app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model/***" \
  "${REPO_ROOT}/" "${HOST}:${REMOTE}/" >>"${LOG}" 2>&1

log "STAGE 2: patch user_config on VPS"
ssh ${SSH_OPTS} "${HOST}" "python3 ${REMOTE}/scripts/patch_prod_trapper_user_config.py" >>"${LOG}" 2>&1 || fail "patch user_config"

# --- ЭТАП 3: build UI + recreate ---
log "STAGE 3: UI build local"
if command -v node >/dev/null 2>&1; then
  node_major="$(node -p 'parseInt(process.versions.node.split(".")[0], 10)' 2>/dev/null || echo 0)"
else
  node_major=0
fi
if [[ "${node_major}" -lt 22 ]]; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1090
  [[ -s "${NVM_DIR}/nvm.sh" ]] && . "${NVM_DIR}/nvm.sh" && (cd app/ui && nvm use 22 >/dev/null 2>&1 || nvm install 22)
fi
(cd app/ui && npm ci --no-audit --no-fund && npm run build) >>"${LOG}" 2>&1 || fail "UI build"
rsync -az -e "${RSYNC_SSH}" "${REPO_ROOT}/app/ui/dist/" "${HOST}:${REMOTE}/app/ui/dist/" >>"${LOG}" 2>&1

log "STAGE 3: docker compose force-recreate"
ssh ${SSH_OPTS} "${HOST}" "cd ${REMOTE}/app && bash scripts/docker-compose-intel-override-gen.sh && docker compose -f docker-compose.yml -f docker-compose.override.yml up -d --build --force-recreate birdlense" >>"${LOG}" 2>&1 || fail "compose up"

log "STAGE 3: wait healthy"
for i in $(seq 1 40); do
  if ssh ${SSH_OPTS} "${HOST}" "docker inspect birdlense --format '{{.State.Health.Status}}' 2>/dev/null" | grep -q healthy; then
    log "container healthy"
    break
  fi
  if [[ "${i}" -eq 40 ]]; then
    ssh ${SSH_OPTS} "${HOST}" "docker logs birdlense --tail=80" >>"${LOG}" 2>&1 || true
    fail "container not healthy after 40 attempts"
  fi
  sleep 5
done

log "STAGE 3: logs trapper/openvino"
ssh ${SSH_OPTS} "${HOST}" "docker logs birdlense --tail=120 2>&1" | tee -a "${LOG}" | grep -iE 'trapper|openvino|TwoStage|detector_scope|error|FileNotFound' || true

log "STAGE 3: video smoke on VPS"
VIDEO_REMOTE="${REMOTE}/app/data/recordings/2026/05/19/151021/video.mp4"
SMOKE_JSON="$(ssh ${SSH_OPTS} "${HOST}" "cd ${REMOTE}/app && docker compose -f docker-compose.yml -f docker-compose.override.yml exec -T birdlense \
  python3 /app/scripts/trapper_ov_smoke_test.py --ov-dir /app/processor/models/detection/weights/trapper_ai_v02_2024_openvino_model \
  --device intel:gpu --imgsz 704 --conf 0.25 --video /app/data/recordings/2026/05/19/151021/video.mp4 --frame-index 50" 2>/dev/null || echo '{\"ok\":false}')"
log "video smoke: ${SMOKE_JSON}"
echo "${SMOKE_JSON}" | grep -q '"ok": true' || fail "video smoke failed"

log "STAGE 3: verify-stack"
BASE_URL="${DEPLOY_URL}" ATTEMPTS=15 SLEEP_SEC=4 CHECK_CAMERAS=0 \
  MCP_TOKEN="${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="${BIRDLENSE_UI_API_KEY:-}" \
  "${REPO_ROOT}/scripts/verify-stack.sh" >>"${LOG}" 2>&1 || fail "verify-stack"

# --- ЭТАП 4: отчёт ---
DETECTIONS="$(echo "${SMOKE_JSON}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('detections',0))" 2>/dev/null || echo 0)"
cat > "${REPORT}" <<EOF
# Fully Autonomous Trapper Deploy Report

**Статус: СИСТЕМА ГОТОВА К РАБОТЕ**

Дата: $(date -Iseconds)  
Цель: TrapperAI v02.2024 OpenVINO FP16 @704  
Хост: ${DEPLOY_URL} (${HOST})

## Подтверждения

| Проверка | Результат |
|----------|-----------|
| Локальный IR imgsz 704 | OK |
| SHA256 local == VPS | OK (${LOCAL_SHA:0:16}…) |
| Smoke dummy (local Docker) | OK |
| Smoke GPU (VPS Docker) | OK |
| user_config патч (Trapper paths, OV, conf 0.25) | OK автоматически |
| docker compose force-recreate | OK |
| Healthcheck birdlense | healthy |
| Video smoke (1819 clip, frame 50) | ${DETECTIONS} detections |
| verify-stack | OK |

## Конфиг (применён на VPS)

- \`processor.models.binary_openvino\`: trapper_ai_v02_2024_openvino_model
- \`processor.binary_imgsz\`: 704
- \`processor.inference_lores_wh\`: [704, 576]
- \`processor.binary_predict_class_allowlist\`: [0, 5] (Bird + Eurasian Red Squirrel)
- \`processor.inference_backend\`: openvino, device intel:gpu

## Метрики (ожидание)

- Detect substream 704×576 → без даунскейла в 640²
- OpenVINO iGPU: ~7–10 FPS infer (showdown quick)
- Пороги: conf 0.25 (showdown без ложных на 1816)

## Лог деплоя

\`${LOG}\`
EOF

log "DONE: ${REPORT}"
cat "${REPORT}"
