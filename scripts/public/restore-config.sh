#!/bin/bash
# Восстановление настроек BirdLense
# 1) С сервера из .bak (если есть)
# 2) Или из локального user_config.yaml на сервер

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
[ -f "${SCRIPT_DIR}/../deploy.local.sh" ] && . "${SCRIPT_DIR}/../deploy.local.sh"
HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
REMOTE_CFG="${REMOTE_DIR}/app/app_config/user_config.yaml"
REMOTE_BAK="${REMOTE_DIR}/app/app_config/user_config.yaml.bak"
LOCAL_CFG="${PROJECT_DIR}/app/app_config/user_config.yaml"

echo "=== Восстановление настроек BirdLense ==="

if [[ "${1:-}" == "from-local" ]]; then
  echo "Режим: копировать ЛОКАЛЬНЫЙ конфиг на сервер"
  if [ ! -f "$LOCAL_CFG" ]; then
    echo "Ошибка: локальный $LOCAL_CFG не найден"
    exit 1
  fi
  echo "Копирую $LOCAL_CFG -> ${HOST}:${REMOTE_CFG}"
  scp "$LOCAL_CFG" "${HOST}:${REMOTE_CFG}"
  echo "Готово. Перезапустите: ssh $HOST 'cd $REMOTE_DIR/app && make stop && make start'"
  exit 0
fi

echo "Режим: восстановить из .bak на сервере"
echo "(Также ищите снимки деплоя: ${REMOTE_CFG}.bak.deploy-*)"
if ssh "$HOST" "test -f $REMOTE_BAK"; then
  ssh "$HOST" "cp $REMOTE_BAK $REMOTE_CFG && echo 'Восстановлено из .bak'"
  echo "Готово. Перезапустите: ssh $HOST 'cd $REMOTE_DIR/app && make stop && make start'"
else
  echo "Бэкап .bak на сервере не найден."
  echo ""
  echo "Чтобы скопировать ЛОКАЛЬНЫЙ конфиг на сервер:"
  echo "  ./scripts/restore-config.sh from-local"
  echo ""
  echo "Локальный конфиг: $LOCAL_CFG"
  exit 1
fi
