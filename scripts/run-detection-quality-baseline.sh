#!/usr/bin/env bash
# Baseline качества детекции по БД Hub (SQLite в DATA_DIR/db или DATABASE_URL).
# Запускать из корня клона (рядом каталог app/). Доступ к внешнему Hub не нужен —
# поднимается локальный Flask create_app() и читается БД с диска.
# Дальше: сохранить JSON в артефакт и сравнивать окна (см. archive/internal/docs-legacy/ML_QUALITY_LOOP.ru.md).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
unset FLASK_TESTING
# Пример внешней БД: export DATABASE_URL='postgresql+psycopg2://...'
# Пример данных: export DATA_DIR=/opt/birdlense/app/data
exec python3 scripts/report-detection-quality-baseline.py "$@"
