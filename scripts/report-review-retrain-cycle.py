#!/usr/bin/env python3
"""Сводка readiness для цикла review -> calibration -> retrain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _project_app_root() -> Path:
    return Path(__file__).resolve().parents[1] / 'app'


def _read_runtime_snapshot(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    """Build review/calibration/retrain readiness report."""
    parser = argparse.ArgumentParser(description=__doc__)
    app_root = _project_app_root()
    default_snapshot = app_root / 'data' / 'diagnostics' / 'processor_runtime_stats.json'
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--dataset-info', default=None)
    parser.add_argument('--fusion-eval-report', default=None)
    parser.add_argument(
        '--runtime-snapshot',
        default=str(default_snapshot),
    )
    args = parser.parse_args()

    web_dir = str(app_root / 'web')
    for p in (str(app_root), web_dir):
        if p not in sys.path:
            sys.path.insert(0, p)
    parent = str(app_root.parent)
    if parent not in sys.path:
        sys.path.append(parent)  # не prepend: иначе конфликт пакета `app` с корня репо

    from web.app import create_app
    from services.ml_quality_cycle_service import build_review_retrain_cycle_report

    app = create_app()
    with app.app_context():
        report = build_review_retrain_cycle_report(
            days=args.days,
            dataset_info_path=args.dataset_info,
            fusion_eval_report_path=args.fusion_eval_report,
            runtime_snapshot=_read_runtime_snapshot(args.runtime_snapshot),
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
