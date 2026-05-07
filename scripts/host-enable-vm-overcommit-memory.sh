#!/usr/bin/env bash
# Включить vm.overcommit_memory=1 на хосте Docker (рекомендация Redis BGSAVE/RDB).
# Запуск на сервере от root один раз после установки или при предупреждении в docker logs redis.
#
#   ssh root@vps 'bash -s' < scripts/host-enable-vm-overcommit-memory.sh
#
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "error: нужен root (sudo)" >&2
  exit 1
fi

CONF="/etc/sysctl.d/99-birdlense-vm-overcommit-redis.conf"
LINE="vm.overcommit_memory = 1"

if [[ -f "${CONF}" ]] && grep -qxF "${LINE}" "${CONF}"; then
  echo "${CONF}: уже есть ${LINE}"
else
  printf '%s\n' "${LINE}" > "${CONF}"
  echo "записано ${CONF}"
fi

sysctl -w vm.overcommit_memory=1 >/dev/null
echo "действует сейчас: vm.overcommit_memory=$(cat /proc/sys/vm/overcommit_memory) (ожидается 1)"
