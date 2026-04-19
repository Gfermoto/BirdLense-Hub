#!/usr/bin/env bash
# Baseline качества детекции по живой БД Hub (SQLite в DATA_DIR/db или DATABASE_URL).
# Запускать из корня клона репозитория (каталог app/ рядом с scripts/).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
unset FLASK_TESTING
# Пример внешней БД: export DATABASE_URL='postgresql+psycopg2://...'
# Пример данных: export DATA_DIR=/opt/birdlense/app/data
exec python3 scripts/report-detection-quality-baseline.py "$@"
