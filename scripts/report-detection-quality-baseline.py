#!/usr/bin/env python3
"""Собрать baseline-метрики качества детекции/распознавания из БД Hub.

Запуск «офлайн» от публичного UI: интернет не нужен. Нужен доступ к той же SQLite (или
DATABASE_URL), что использует Hub: локальный каталог app/data/db или копия БД + DATA_DIR.

Типичный цикл: периодически (например, раз в неделю) сохранять вывод в файл и сравнивать
с прошлым прогоном; метрики завязаны на decision_trace и Video/VideoSpecies — см. docs/ML_QUALITY_LOOP.ru.md
и scripts/run-detection-quality-baseline.sh.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _project_app_root() -> Path:
    return Path(__file__).resolve().parents[1] / 'app'


def _load_runtime_snapshot(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    """Build baseline report from Hub DB and optional runtime snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=14, help='Окно анализа в сутках')
    app_root = _project_app_root()
    default_snapshot = app_root / 'data' / 'diagnostics' / 'processor_runtime_stats.json'
    parser.add_argument(
        '--runtime-snapshot',
        default=str(default_snapshot),
        help='Опциональный JSON snapshot runtime-метрик процессора',
    )
    args = parser.parse_args()

    web_dir = str(app_root / 'web')
    for p in (str(app_root), web_dir):
        if p not in sys.path:
            sys.path.insert(0, p)
    # Репозиторий (fusion export и др.) — в хвост, иначе каталог `app` с корня репо перекрывает импорты.
    parent = str(app_root.parent)
    if parent not in sys.path:
        sys.path.append(parent)

    from web.app import create_app
    from services.detection_quality_baseline_service import (
        build_detection_quality_baseline,
    )

    app = create_app()
    with app.app_context():
        report = build_detection_quality_baseline(
            days=args.days,
            runtime_snapshot=_load_runtime_snapshot(args.runtime_snapshot),
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
