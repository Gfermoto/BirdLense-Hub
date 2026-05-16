#!/usr/bin/env python3
"""Build canary rollback artifact for issue #409."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding='utf-8') as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f'JSON object expected: {path}')
    return payload


def _metric(obj: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(obj.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def build_canary_rollback_report(
    *,
    baseline_sli: dict[str, Any],
    canary_sli: dict[str, Any],
    rollback_sli: dict[str, Any] | None,
    max_latency_regression_ratio: float = 0.10,
    max_error_rate: float = 0.01,
) -> dict[str, Any]:
    """Build canary rollout report with rollback drill verdict."""
    base_p95 = _metric(baseline_sli, 'p95_latency_ms', 0.0)
    canary_p95 = _metric(canary_sli, 'p95_latency_ms', 0.0)
    canary_err = _metric(canary_sli, 'error_rate', 0.0)
    latency_regression = (
        (canary_p95 - base_p95) / base_p95
        if base_p95 > 0
        else None
    )
    rollback_ok = True
    rollback_p95 = None
    rollback_err = None
    if rollback_sli is not None:
        rollback_p95 = _metric(rollback_sli, 'p95_latency_ms', 0.0)
        rollback_err = _metric(rollback_sli, 'error_rate', 0.0)
        rollback_ok = (
            (
                rollback_p95
                <= base_p95 * (1.0 + float(max_latency_regression_ratio))
            )
            and (rollback_err <= float(max_error_rate))
        )
    gates = {
        'canary_latency_ok': bool(
            latency_regression is None
            or latency_regression <= float(max_latency_regression_ratio)
        ),
        'canary_error_ok': bool(canary_err <= float(max_error_rate)),
        'rollback_restores_baseline_sli': bool(rollback_ok),
    }
    playbook = {
        'stages': [1, 5, 20],
        'auto_stop_condition': (
            f'latency regression > {float(max_latency_regression_ratio):.3f} '
            f'or error_rate > {float(max_error_rate):.3f}'
        ),
        'rollback_steps': [
            'Switch detector path to baseline backend/model in user_config.yaml.',
            'Restart processor/web stack.',
            'Re-run readiness + continuity + canary SLI snapshot.',
        ],
    }
    return {
        'schema': 'canary_rollback_report@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'thresholds': {
            'max_latency_regression_ratio': float(max_latency_regression_ratio),
            'max_error_rate': float(max_error_rate),
        },
        'metrics': {
            'baseline_p95_latency_ms': round(base_p95, 6),
            'canary_p95_latency_ms': round(canary_p95, 6),
            'canary_error_rate': round(canary_err, 6),
            'latency_regression_ratio': (
                None
                if latency_regression is None
                else round(latency_regression, 6)
            ),
            'rollback_p95_latency_ms': (
                None if rollback_p95 is None else round(float(rollback_p95), 6)
            ),
            'rollback_error_rate': (
                None if rollback_err is None else round(float(rollback_err), 6)
            ),
        },
        'gates': gates,
        'playbook': playbook,
        'rollback_drill_passed': bool(gates['rollback_restores_baseline_sli']),
        'ok': all(bool(v) for v in gates.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--baseline-sli',
        required=True,
        help='JSON file with baseline canary SLI snapshot.',
    )
    parser.add_argument(
        '--canary-sli',
        required=True,
        help='JSON file with canary SLI snapshot.',
    )
    parser.add_argument(
        '--rollback-sli',
        default='',
        help='Optional JSON file after rollback drill.',
    )
    parser.add_argument('--max-latency-regression-ratio', type=float, default=0.10)
    parser.add_argument('--max-error-rate', type=float, default=0.01)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = _parse_args()
    baseline = _load_json(args.baseline_sli)
    canary = _load_json(args.canary_sli)
    rollback = (
        _load_json(args.rollback_sli)
        if (args.rollback_sli or '').strip()
        else None
    )
    out = build_canary_rollback_report(
        baseline_sli=baseline,
        canary_sli=canary,
        rollback_sli=rollback,
        max_latency_regression_ratio=float(args.max_latency_regression_ratio),
        max_error_rate=float(args.max_error_rate),
    )
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if bool(out.get('ok')) else 3


if __name__ == '__main__':
    raise SystemExit(main())
