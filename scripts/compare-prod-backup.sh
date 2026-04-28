#!/usr/bin/env bash
# Read-only production DB/config snapshot vs backup comparison.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
BACKUP_DB="${1:-}"

if [ -z "${BACKUP_DB}" ]; then
  echo "Usage: $0 /root/BirdLense/app/data/db/birdlense.db.bak-YYYYMMDD-HHMMSS" >&2
  echo "Tip: ssh HOST 'ls -1t ${REMOTE_DIR}/app/data/db/*.bak* | head'" >&2
  exit 2
fi

_PORT_OPT=""
if [ -n "${DEPLOY_SSH_PORT:-}" ] && [ "${DEPLOY_SSH_PORT}" != "22" ]; then
  _PORT_OPT="-p ${DEPLOY_SSH_PORT}"
fi
SSH_OPTS="${_PORT_OPT} -o ServerAliveInterval=30 -o ServerAliveCountMax=20"

ssh ${SSH_OPTS} "${HOST}" env REMOTE_DIR="${REMOTE_DIR}" BACKUP_DB="${BACKUP_DB}" bash -s <<'ENDSSH'
set -euo pipefail
APP="${REMOTE_DIR}/app"
CURRENT="${APP}/data/db/birdlense.db"

test -f "$CURRENT"
test -f "$BACKUP_DB"

echo "== files =="
ls -lh "$CURRENT" "$BACKUP_DB"

echo "== env keys (masked) =="
if [ -f "${APP}/.env" ]; then
  sed -n 's/^\([A-Z0-9_][A-Z0-9_]*\)=.*/\1=SET/p' "${APP}/.env" | sort
fi

case "$BACKUP_DB" in
  "${APP}/data/"*) CONTAINER_BACKUP="/app/data/${BACKUP_DB#"${APP}/data/"}" ;;
  *) echo "Backup must be under ${APP}/data for container read-only compare" >&2; exit 2 ;;
esac

docker exec -i -e CURRENT_DB=/app/data/db/birdlense.db -e BACKUP_DB="$CONTAINER_BACKUP" birdlense python - <<'PY'
import difflib
import os
import sqlite3

def connect(path: str):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)

def schema(path: str) -> list[str]:
    with connect(path) as db:
        rows = db.execute(
            "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL ORDER BY type, name"
        ).fetchall()
    return [f"{row[0]};\n" for row in rows]

def counts(path: str) -> dict[str, int | str]:
    out: dict[str, int | str] = {}
    with connect(path) as db:
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            try:
                out[table] = db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except sqlite3.Error as exc:
                out[table] = f"err:{exc}"
    return out

current = os.environ["CURRENT_DB"]
backup = os.environ["BACKUP_DB"]

print("== schema diff ==")
for line in difflib.unified_diff(schema(backup), schema(current), fromfile="backup", tofile="current"):
    print(line, end="")

print("== table counts ==")
for label, path in (("backup", backup), ("current", current)):
    print(f"-- {label}")
    for table, count in counts(path).items():
        print(f"{table}={count}")
PY
ENDSSH
