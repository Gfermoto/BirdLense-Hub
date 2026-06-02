#!/usr/bin/env bash
# Online SQLite backup from production host for nightly governance (#585).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

if [[ -f "${SCRIPT_DIR}/deploy.local.sh" ]]; then
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/deploy.local.sh"
fi

HOST="${DEPLOY_HOST:-}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
REMOTE_DB="${REMOTE_DIR}/app/data/db/birdlense.db"
LOCAL_DIR="${PROD_DB_SNAPSHOT_DIR:-app/data/db/prod_snapshots}"
LOCAL_LATEST="${PROD_DB_SNAPSHOT_LATEST:-app/data/db/birdlense_prod_latest.db}"

if [[ -z "${HOST}" ]]; then
  echo "fetch_prod_db_snapshot: DEPLOY_HOST not set (scripts/deploy.local.sh)" >&2
  exit 2
fi

_PORT_OPT=()
if [[ -n "${DEPLOY_SSH_PORT:-}" && "${DEPLOY_SSH_PORT}" != "22" ]]; then
  _PORT_OPT=(-p "${DEPLOY_SSH_PORT}")
fi
SSH_OPTS=("${_PORT_OPT[@]}" -o ServerAliveInterval=30 -o ServerAliveCountMax=20)

TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL_DIR_ABS="${ROOT}/${LOCAL_DIR}"
mkdir -p "${LOCAL_DIR_ABS}"
REMOTE_TMP="${REMOTE_DIR}/app/data/db/.birdlense_prod_snapshot_${TS}.db"
LOCAL_FILE="${LOCAL_DIR_ABS}/birdlense_${TS}.db"
LOCAL_LATEST_ABS="${ROOT}/${LOCAL_LATEST}"

echo "fetch_prod_db_snapshot: backup on ${HOST}:${REMOTE_DB} -> ${LOCAL_FILE}"

ssh "${SSH_OPTS[@]}" "${HOST}" bash -s -- "${REMOTE_DB}" "${REMOTE_TMP}" <<'REMOTE'
set -euo pipefail
SRC="$1"
DST="$2"
test -f "${SRC}"
python3 - <<'PY' "${SRC}" "${DST}"
import sqlite3
import sys

src, dst = sys.argv[1:3]
with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as src_conn:
    with sqlite3.connect(dst) as dst_conn:
        src_conn.backup(dst_conn)
PY
ls -lh "${DST}"
REMOTE

mkdir -p "$(dirname "${LOCAL_LATEST_ABS}")"
rsync -avz "${SSH_OPTS[@]}" "${HOST}:${REMOTE_TMP}" "${LOCAL_FILE}"
ssh "${SSH_OPTS[@]}" "${HOST}" "rm -f '${REMOTE_TMP}'"
cp -f "${LOCAL_FILE}" "${LOCAL_LATEST_ABS}"

python3 - <<'PY' "${LOCAL_FILE}" "${LOCAL_LATEST_ABS}" "${HOST}" "${REMOTE_DB}"
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

local_file, local_latest, host, remote_db = sys.argv[1:5]
meta_path = Path(local_file).with_suffix(".json")
sessions = 0
try:
    with sqlite3.connect(local_file) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM session_runtime_metrics "
            "WHERE datetime(created_at) >= datetime('now', '-24 hours')"
        ).fetchone()
        sessions = int(row[0] if row else 0)
except sqlite3.Error:
    pass
meta = {
    "schema": "prod_db_snapshot@v1",
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "host": host,
    "remote_db": remote_db,
    "local_file": local_file,
    "local_latest": local_latest,
    "session_runtime_metrics_24h": sessions,
}
meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(json.dumps(meta))
PY

echo "fetch_prod_db_snapshot: OK -> ${LOCAL_LATEST_ABS}"
