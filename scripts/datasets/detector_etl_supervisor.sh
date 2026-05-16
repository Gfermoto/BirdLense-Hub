#!/usr/bin/env bash
# Держит волны build_detector_dataset_waves.sh до успешного конца или поднимает после падения.
# Запуск из корня или как:
#   bash scripts/datasets/detector_etl_supervisor.sh
# Фоном:
#   nohup bash scripts/datasets/detector_etl_supervisor.sh >> datasets/logs/detector_etl_supervisor.log 2>&1 &
#
# Env: POLL_SEC (пауза цикла, по умолчанию 120)
#
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

DONE="$REPO_ROOT/datasets/logs/.detector_etl_done"
PIDF="$REPO_ROOT/datasets/logs/detector_waves.pid"
Poll="${POLL_SEC:-120}"

log_msg() {
  printf '[%s] %s\n' "$(date -Is)" "$*" >&2
}

need_restart() {
  local w=""
  if [[ ! -r "$PIDF" ]]; then
    return 0
  fi
  read -r w <"$PIDF" || true
  if [[ -z "${w:-}" ]]; then
    return 0
  fi
  if ! kill -0 "$w" 2>/dev/null; then
    return 0
  fi
  # Жив ли это именно наш waves-процесс
  cmd=$(tr '\0' ' ' <"/proc/$w/cmdline" 2>/dev/null || echo "")
  if [[ "$cmd" != *build_detector_dataset_waves.sh* ]]; then
    return 0
  fi
  return 1
}

rm -f "$DONE"
log_msg "supervisor: старт"

if need_restart; then
  log_msg "supervisor: волн нет или pid мёртв — restart_detector_dataset_waves.sh"
  bash "$SCRIPT_DIR/restart_detector_dataset_waves.sh"
fi

while [[ ! -f "$DONE" ]]; do
  sleep "$Poll"

  if [[ -f "$DONE" ]]; then
    log_msg "supervisor: готово (.detector_etl_done)"
    break
  fi

  if need_restart; then
    log_msg "supervisor: волны оборвались без маркера — перезапуск"
    bash "$SCRIPT_DIR/restart_detector_dataset_waves.sh"
    continue
  fi
done

log_msg "supervisor: успешное завершение ETL waves + merge"
