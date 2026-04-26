#!/usr/bin/env bash
# Поиск и (опционально) откат SQLite birdlense.db к снимку pre_restore или копии на диске.
# Автоматические копии: birdlense.db.pre_restore_<UTC>.bak (создаётся UI при «Восстановить БД»).
# Использование:
#   ./scripts/recover-sqlite-from-backups.sh list              # локально + на DEPLOY_HOST (если deploy.local.sh)
#   ./scripts/recover-sqlite-from-backups.sh list-remote       # только удалённый каталог db/
#   ./scripts/recover-sqlite-from-backups.sh pull-latest       # самый новый *.pre_restore*.bak → ./backups-recovered/
#   ./scripts/recover-sqlite-from-backups.sh pull-all          # все *.bak* из удалённого db/ (и ручные birdlense.db.bak-*)
#   ./scripts/recover-sqlite-from-backups.sh compare-remote      # videos / visits / video_species по *.bak* на сервере (без открытия живой .db)
#   ./scripts/recover-sqlite-from-backups.sh compare-local       # то же для ./backups-recovered/*.bak*
#   ./scripts/recover-sqlite-from-backups.sh apply-remote FILE   # остановить birdlense, заменить db, старт
#   ./scripts/recover-sqlite-from-backups.sh apply-best-remote   # выбрать лучший .bak на сервере и применить (нужен BIRDLENSE_RESTORE_CONFIRM_YES=1)
#
# Безопасность: apply-remote требует ввода YES, либо env BIRDLENSE_RESTORE_CONFIRM_YES=1 (для CI/автоматизации).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_DB_DIR="${PROJECT_DIR}/app/data/db"
RECOVER_DIR="${PROJECT_DIR}/backups-recovered"

SSH_OPTS=""
_PORT_OPT=""
if [ -f "${SCRIPT_DIR}/deploy.local.sh" ]; then
  # shellcheck source=/dev/null
  . "${SCRIPT_DIR}/deploy.local.sh"
fi
HOST="${DEPLOY_HOST:-}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
REMOTE_DB_DIR="${REMOTE_DIR}/app/data/db"

if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=120 -o ConnectTimeout=25 -o ConnectionAttempts=2"
RSYNC_RSH="ssh ${SSH_OPTS}"

list_local() {
  echo "=== Локально: ${LOCAL_DB_DIR} ==="
  if [ ! -d "${LOCAL_DB_DIR}" ]; then
    echo "(каталога нет)"
    return
  fi
  ls -la "${LOCAL_DB_DIR}" 2>/dev/null || true
  echo "--- pre_restore / прочие .bak ---"
  find "${LOCAL_DB_DIR}" -maxdepth 1 \( -name '*.pre_restore*.bak' -o -name '*.bak' \) -printf '%TY-%Tm-%Td %TT %p %k KB\n' 2>/dev/null | sort -r || true
}

list_remote() {
  if [ -z "${HOST}" ] || [ "${HOST}" = "localhost" ] || [ "${HOST}" = "127.0.0.1" ]; then
    echo "=== Удалённый список пропущен (DEPLOY_HOST не задан или localhost) ==="
    return
  fi
  echo "=== Удалённо: ${HOST}:${REMOTE_DB_DIR} ==="
  ssh ${SSH_OPTS} "${HOST}" "ls -la '${REMOTE_DB_DIR}' 2>/dev/null; echo '--- pre_restore ---'; ls -1t '${REMOTE_DB_DIR}'/birdlense.db.pre_restore_*.bak 2>/dev/null | head -20 || true"
}

pull_latest() {
  if [ -z "${HOST}" ] || [ "${HOST}" = "localhost" ]; then
    echo "Нужен DEPLOY_HOST в scripts/deploy.local.sh"
    exit 1
  fi
  mkdir -p "${RECOVER_DIR}"
  latest="$(ssh ${SSH_OPTS} "${HOST}" "ls -1t '${REMOTE_DB_DIR}'/birdlense.db.pre_restore_*.bak 2>/dev/null | head -1")"
  if [ -z "${latest}" ]; then
    echo "На сервере не найдено birdlense.db.pre_restore_*.bak в ${REMOTE_DB_DIR}"
    exit 1
  fi
  base="$(basename "${latest}")"
  echo "rsync ${HOST}:${latest} -> ${RECOVER_DIR}/${base}"
  rsync -v --partial -e "${RSYNC_RSH}" "${HOST}:${latest}" "${RECOVER_DIR}/${base}"
  echo "Готово. Проверка: sqlite3 \"${RECOVER_DIR}/${base}\" 'PRAGMA integrity_check;'"
}

pull_all() {
  if [ -z "${HOST}" ] || [ "${HOST}" = "localhost" ]; then
    echo "Нужен DEPLOY_HOST"
    exit 1
  fi
  mkdir -p "${RECOVER_DIR}"
  echo "rsync по одному файлу: ${HOST}:${REMOTE_DB_DIR}/birdlense.db*.bak*"
  while IFS= read -r remote; do
    remote="$(echo "${remote}" | tr -d '\r')"
    [ -z "${remote}" ] && continue
    base="$(basename "${remote}")"
    rsync -v --partial -e "${RSYNC_RSH}" "${HOST}:${remote}" "${RECOVER_DIR}/${base}" || true
  done < <(ssh ${SSH_OPTS} "${HOST}" "sh -c 'ls -1 \"${REMOTE_DB_DIR}\"/birdlense.db*.bak* 2>/dev/null || true'")
  cnt="$(find "${RECOVER_DIR}" -maxdepth 1 -name 'birdlense.db*.bak*' 2>/dev/null | wc -l)"
  if [ "${cnt}" -eq 0 ]; then
    echo "Ничего не скачано — проверьте ${REMOTE_DB_DIR} на сервере и SSH."
    exit 1
  fi
  echo "Сохранено ${cnt} файл(ов) в ${RECOVER_DIR}/"
}

_compare_py_body() {
  cat <<'PY'
import glob
import os
import sqlite3

def stat(p):
    con = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
    try:
        ok = con.execute("pragma integrity_check").fetchone()[0]
        v = con.execute("select count(*) from video").fetchone()[0]
        vis = con.execute("select count(*) from species_visit").fetchone()[0]
        vs = con.execute("select count(*) from video_species").fetchone()[0]
    finally:
        con.close()
    return ok, v, vis, vs

root = os.environ["D"]
rows = []
for p in sorted(glob.glob(os.path.join(root, "birdlense.db*.bak*"))):
    if not os.path.isfile(p):
        continue
    try:
        ok, v, vis, vs = stat(p)
        rows.append((vis, v, vs, os.path.basename(p), ok))
    except Exception as e:  # noqa: BLE001
        rows.append((-1, -1, -1, os.path.basename(p), str(e)))
for vis, v, vs, name, ok in sorted(rows, key=lambda r: (r[0], r[1], r[2]), reverse=True):
    print("%s\tintegrity=%s\tvisits=%s\tvideos=%s\tvideo_species=%s" % (name, ok, vis, v, vs))
good = [r for r in rows if r[4] == "ok"]
if good:
    best = max(good, key=lambda r: (r[0], r[1], r[2]))
    print("RECOMMENDED_BASENAME=" + best[3])
PY
}

compare_remote() {
  if [ -z "${HOST}" ] || [ "${HOST}" = "localhost" ]; then
    echo "Нужен DEPLOY_HOST"
    exit 1
  fi
  echo "=== Сравнение снимков на ${HOST}:${REMOTE_DB_DIR} (только *.bak*) ==="
  # shellcheck disable=SC2029
  _compare_py_body | ssh ${SSH_OPTS} "${HOST}" "export D=\"${REMOTE_DB_DIR}\"; python3"
}

compare_local() {
  echo "=== Локально: ${RECOVER_DIR} ==="
  if [ ! -d "${RECOVER_DIR}" ] || [ -z "$(ls -A "${RECOVER_DIR}" 2>/dev/null)" ]; then
    echo "(пусто — сначала pull-all)"
    exit 1
  fi
  export D="${RECOVER_DIR}"
  _compare_py_body | python3
}

apply_best_remote() {
  if [ "${BIRDLENSE_RESTORE_CONFIRM_YES:-}" != "1" ]; then
    echo "Задайте BIRDLENSE_RESTORE_CONFIRM_YES=1 (осознанное подтверждение массовой подмены БД на сервере)."
    exit 1
  fi
  best="$(compare_remote | sed -n 's/^RECOMMENDED_BASENAME=//p' | tail -1)"
  if [ -z "${best}" ]; then
    echo "Не удалось выбрать снимок (compare-remote не вернул RECOMMENDED)."
    exit 1
  fi
  echo "Выбран файл: ${best}"
  apply_remote "${best}"
}

apply_remote() {
  local fname="${1:-}"
  if [ -z "${fname}" ]; then
    echo "Укажите имя файла в ${REMOTE_DB_DIR} (например birdlense.db.pre_restore_20260415_120000Z.bak)"
    exit 1
  fi
  if [ -z "${HOST}" ] || [ "${HOST}" = "localhost" ]; then
    echo "Нужен DEPLOY_HOST"
    exit 1
  fi
  echo "ВНИМАНИЕ: на сервере будет остановлен контейнер birdlense, текущая birdlense.db заменена копией из:"
  echo "  ${REMOTE_DB_DIR}/${fname}"
  echo "Перед заменой будет создан дополнительный .bak рядом."
  if [ "${BIRDLENSE_RESTORE_CONFIRM_YES:-}" = "1" ]; then
    confirm="YES"
  else
    read -r -p 'Введите YES для продолжения: ' confirm
  fi
  if [ "${confirm}" != "YES" ]; then
    echo "Отмена."
    exit 1
  fi
  ssh ${SSH_OPTS} "${HOST}" bash -s -- "${REMOTE_DB_DIR}" "${fname}" <<'REMOTE'
set -euo pipefail
REMOTE_DB_DIR="$1"
FNAME="$2"
cd "$REMOTE_DB_DIR"
test -f "$FNAME"
ts="$(date -u +%Y%m%d_%H%M%SZ)"
docker stop birdlense 2>/dev/null || true
if [ -f birdlense.db ]; then
  cp -a birdlense.db "birdlense.db.before_manual_restore_${ts}.bak"
fi
rm -f birdlense.db-wal birdlense.db-shm 2>/dev/null || true
cp -a "$FNAME" birdlense.db
docker start birdlense 2>/dev/null || true
echo "Замена выполнена. Проверьте health и логи контейнера."
REMOTE
}

cmd="${1:-list}"
case "${cmd}" in
  list)
    list_local
    echo ""
    list_remote
    ;;
  list-remote)
    list_remote
    ;;
  pull-latest)
    pull_latest
    ;;
  pull-all)
    pull_all
    ;;
  apply-remote)
    apply_remote "${2:-}"
    ;;
  compare-remote)
    compare_remote
    ;;
  compare-local)
    compare_local
    ;;
  apply-best-remote)
    apply_best_remote
    ;;
  *)
    echo "Неизвестная команда: ${cmd}"
    echo "Команды: list | list-remote | compare-remote | compare-local | pull-latest | pull-all | apply-remote <basename> | apply-best-remote"
    exit 1
    ;;
esac
