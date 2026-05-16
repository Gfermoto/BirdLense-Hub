#!/usr/bin/env python3
"""Verify Re-ID production gates for #389/#390."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path}: root must be object')
    return data


def _as_float(val: Any) -> float | None:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def verify_reid_gates(
    *,
    reid_summary: dict[str, Any],
    reid_match: dict[str, Any] | None,
    min_embeddings: int,
    max_missing_contract_rows: int,
    require_contract_ok: bool,
    max_stale_hours: float | None,
    min_suggestion_count: int,
) -> tuple[bool, dict[str, Any]]:
    """Validate Re-ID summary/match payloads against rollout gates."""
    errors: list[str] = []
    checks: dict[str, Any] = {}

    checks['summary_schema'] = reid_summary.get('schema')
    if checks['summary_schema'] != 'reid_summary@v2':
        errors.append('bad_reid_summary_schema')

    available = bool(reid_summary.get('available'))
    checks['summary_available'] = available
    if not available:
        errors.append('reid_summary_not_available')

    embedding_count = int(reid_summary.get('embedding_count') or 0)
    checks['embedding_count'] = embedding_count
    checks['min_embeddings'] = int(min_embeddings)
    if embedding_count < int(min_embeddings):
        errors.append(
            f'embedding_count_below_threshold:{embedding_count}'
            f'<{int(min_embeddings)}'
        )

    raw_contract = reid_summary.get('contract')
    contract = raw_contract if isinstance(raw_contract, dict) else {}
    contract_status = str(contract.get('status') or '')
    checks['contract_status'] = contract_status
    if require_contract_ok and contract_status != 'ok':
        errors.append(f'contract_status_not_ok:{contract_status or "missing"}')

    missing_rows = int(contract.get('missing_contract_rows') or 0)
    checks['missing_contract_rows'] = missing_rows
    checks['max_missing_contract_rows'] = int(max_missing_contract_rows)
    if missing_rows > int(max_missing_contract_rows):
        errors.append(
            'missing_contract_rows_above_threshold:'
            f'{missing_rows}>{int(max_missing_contract_rows)}'
        )

    max_age_hours = _as_float(contract.get('max_embedding_age_hours'))
    checks['max_embedding_age_hours'] = max_age_hours
    if max_stale_hours is not None and max_age_hours is not None:
        checks['max_stale_hours'] = float(max_stale_hours)
        if max_age_hours > float(max_stale_hours):
            errors.append(
                'embedding_age_above_threshold:'
                f'{max_age_hours:.4f}>{float(max_stale_hours):.4f}'
            )

    if reid_match is not None:
        checks['reid_match_schema'] = reid_match.get('schema')
        if checks['reid_match_schema'] != 'video_reid_match@v2':
            errors.append('bad_reid_match_schema')

        match_available = bool(reid_match.get('available'))
        checks['reid_match_available'] = match_available
        if not match_available:
            errors.append('reid_match_not_available')

        contract_ready = bool(reid_match.get('contract_ready'))
        checks['reid_match_contract_ready'] = contract_ready
        if not contract_ready:
            errors.append('reid_match_contract_not_ready')

        matches = reid_match.get('matches')
        if not isinstance(matches, list):
            errors.append('reid_match_matches_not_list')
            matches = []

        suggestion_count = 0
        bad_policy_rows = 0
        for item in matches:
            if not isinstance(item, dict):
                bad_policy_rows += 1
                continue
            decision = str(item.get('decision') or '')
            policy_decision = str(item.get('policy_decision') or '')
            similarity = _as_float(item.get('similarity'))
            threshold = _as_float(item.get('effective_threshold'))
            if decision == 'suggest_same_individual':
                suggestion_count += 1
            if (
                decision != 'suggest_same_individual'
                or policy_decision != 'suggest_same_individual'
            ):
                bad_policy_rows += 1
            if similarity is None or similarity < 0.0 or similarity > 1.0:
                bad_policy_rows += 1
            if threshold is None or threshold < 0.0 or threshold > 1.0:
                bad_policy_rows += 1

        checks['suggestion_count'] = suggestion_count
        checks['min_suggestion_count'] = int(min_suggestion_count)
        checks['invalid_match_rows'] = bad_policy_rows
        if suggestion_count < int(min_suggestion_count):
            errors.append(
                'suggestion_count_below_threshold:'
                f'{suggestion_count}<{int(min_suggestion_count)}'
            )
        if bad_policy_rows > 0:
            errors.append(f'invalid_reid_match_rows:{bad_policy_rows}')

    ok = len(errors) == 0
    out = {
        'schema': 'reid_production_gates@v1',
        'ok': ok,
        'checks': checks,
        'errors': errors,
    }
    return ok, out


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--reid-summary',
        required=True,
        help='JSON payload from /api/ui/system/reid/summary',
    )
    parser.add_argument(
        '--reid-match',
        default='',
        help='Optional JSON payload from /api/ui/videos/{id}/reid-match',
    )
    parser.add_argument('--min-embeddings', type=int, default=1)
    parser.add_argument('--max-missing-contract-rows', type=int, default=0)
    parser.add_argument('--require-contract-ok', action='store_true')
    parser.add_argument('--max-stale-hours', type=float, default=None)
    parser.add_argument('--min-suggestion-count', type=int, default=0)
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    reid_summary = _load_json(Path(args.reid_summary).resolve())
    if str(args.reid_match).strip():
        reid_match = _load_json(Path(args.reid_match).resolve())
    else:
        reid_match = None
    ok, out = verify_reid_gates(
        reid_summary=reid_summary,
        reid_match=reid_match,
        min_embeddings=int(args.min_embeddings),
        max_missing_contract_rows=int(args.max_missing_contract_rows),
        require_contract_ok=bool(args.require_contract_ok),
        max_stale_hours=(
            float(args.max_stale_hours)
            if args.max_stale_hours is not None
            else None
        ),
        min_suggestion_count=int(args.min_suggestion_count),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
