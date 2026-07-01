#!/usr/bin/env python3
"""Build detector candidate shortlist and bird-only verdict report (#405)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f'{path}: root must be an object')
    return data


def _default_candidates() -> list[dict[str, Any]]:
    return [
        {
            'id': 'bl-current-yolo11n-binary',
            'name': 'BirdLense current YOLO11n binary detector',
            'quality_score': 0.74,
            'latency_ms': 12.0,
            'onnx_deployable': True,
            'integration_risk': 'low',
            'license': {
                'spdx': 'AGPL-3.0',
                'status': 'review_required',
                'notes': 'Runtime stack uses Ultralytics; keep AGPL compliance controls.',
            },
            'bird_only_supported': True,
            'notes': 'Fastest migration path; already integrated and observable.',
        },
        {
            'id': 'birds-classification-yolov9',
            'name': 'Birds-Classification YOLOv9 candidate',
            'quality_score': 0.79,
            'latency_ms': 18.0,
            'onnx_deployable': True,
            'integration_risk': 'high',
            'license': {
                'spdx': 'NOASSERTION',
                'status': 'blocked',
                'notes': 'Upstream license/commercial terms are not explicit enough for production.',
            },
            'bird_only_supported': True,
            'notes': 'Quality-promising, but onboarding blocked by compliance ambiguity.',
        },
        {
            'id': 'yolov8n-onnx-int8',
            'name': 'YOLOv8n ONNX INT8 candidate',
            'quality_score': 0.72,
            'latency_ms': 9.0,
            'onnx_deployable': True,
            'integration_risk': 'medium',
            'license': {
                'spdx': 'AGPL-3.0',
                'status': 'review_required',
                'notes': 'Same runtime obligations as current stack, plus PTQ validation work.',
            },
            'bird_only_supported': True,
            'notes': 'Strong latency profile; depends on PTQ stability and INT8 gates.',
        },
        {
            'id': 'frigate-bird-only-hybrid',
            'name': 'Bird-only detector + Frigate rodent hybrid',
            'quality_score': 0.70,
            'latency_ms': 10.0,
            'onnx_deployable': True,
            'integration_risk': 'medium',
            'license': {
                'spdx': 'MIXED',
                'status': 'approved',
                'notes': 'Uses existing deployed components; no new upstream model license risk.',
            },
            'bird_only_supported': True,
            'notes': 'Primary fallback strategy when rodent detector quality regresses.',
        },
    ]


def _risk_penalty(risk: str) -> float:
    risk_l = str(risk or '').strip().lower()
    if risk_l == 'low':
        return 0.0
    if risk_l == 'medium':
        return 0.08
    if risk_l == 'high':
        return 0.2
    return 0.12


def _license_penalty(status: str) -> float:
    status_l = str(status or '').strip().lower()
    if status_l == 'approved':
        return 0.0
    if status_l == 'review_required':
        return 0.08
    if status_l == 'blocked':
        return 0.4
    return 0.2


def _latency_score(latency_ms: float) -> float:
    # 8ms -> ~1.0, 28ms -> ~0.0 (clamped)
    x = (28.0 - float(latency_ms)) / 20.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _candidate_rank_score(candidate: dict[str, Any]) -> float:
    quality = float(candidate.get('quality_score') or 0.0)
    latency = _latency_score(float(candidate.get('latency_ms') or 0.0))
    onnx = 1.0 if bool(candidate.get('onnx_deployable')) else 0.0
    risk_p = _risk_penalty(str(candidate.get('integration_risk') or 'medium'))
    lic_p = _license_penalty(str((candidate.get('license') or {}).get('status') or 'review_required'))
    score = 0.6 * quality + 0.25 * latency + 0.15 * onnx - risk_p - lic_p
    return round(score, 6)


def _build_bird_only_verdict(
    continuity_report: dict[str, Any] | None,
    offline_gate_report: dict[str, Any] | None,
) -> dict[str, Any]:
    continuity_ok = bool((continuity_report or {}).get('ok'))
    metrics = (continuity_report or {}).get('metrics') or {}
    track_ok = bool(metrics.get('track_gate_ok', False))
    crop_ok = bool(metrics.get('crop_gate_ok', False))
    rows = (continuity_report or {}).get('rows') or {}
    provider_counts = rows.get('provider_counts') or {}
    total_rows = int(rows.get('video_rows_total') or 0)
    frigate_rows = int(provider_counts.get('frigate') or 0)
    frigate_share = (float(frigate_rows) / float(total_rows)) if total_rows > 0 else 0.0
    offline_ok = bool((offline_gate_report or {}).get('ok')) if offline_gate_report else False

    viable = continuity_ok and track_ok and crop_ok and frigate_rows > 0
    confidence = 'high' if viable and offline_ok else ('medium' if viable else 'low')
    rationale = []
    if continuity_ok:
        rationale.append('continuity_gate_pass')
    if track_ok and crop_ok:
        rationale.append('tracks_and_crops_stable')
    if frigate_rows > 0:
        rationale.append('frigate_signal_present')
    if offline_ok:
        rationale.append('offline_benchmark_gate_pass')
    if not rationale:
        rationale.append('insufficient_evidence')

    return {
        'status': 'viable' if viable else 'not_viable',
        'confidence': confidence,
        'frigate_share': round(frigate_share, 6),
        'rationale': rationale,
        'requires_follow_up': (not offline_ok) or (not viable),
    }


def build_detector_shortlist_report(
    *,
    continuity_report: dict[str, Any] | None,
    offline_gate_report: dict[str, Any] | None,
    shortlist_size: int = 3,
) -> dict[str, Any]:
    candidates = _default_candidates()
    evaluated: list[dict[str, Any]] = []
    for item in candidates:
        row = dict(item)
        row['rank_score'] = _candidate_rank_score(row)
        evaluated.append(row)
    evaluated.sort(key=lambda x: float(x.get('rank_score') or 0.0), reverse=True)

    allowed = [row for row in evaluated if str((row.get('license') or {}).get('status')) != 'blocked']
    shortlist = allowed[: max(1, int(shortlist_size or 3))]
    compliance_blocked = [row['id'] for row in evaluated if str((row.get('license') or {}).get('status')) == 'blocked']
    compliance_verdict = {
        'status': 'review_required' if any(str((row.get('license') or {}).get('status')) == 'review_required' for row in shortlist) else 'approved',
        'blocked_candidates': compliance_blocked,
        'notes': (
            'Shortlist excludes blocked licenses; review_required candidates need legal/compliance confirmation before production rollout.'
        ),
    }

    bird_only = _build_bird_only_verdict(continuity_report, offline_gate_report)

    out = {
        'schema': 'detector_shortlist_report@v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'inputs': {
            'continuity_schema': (continuity_report or {}).get('schema'),
            'offline_gate_schema': (offline_gate_report or {}).get('schema'),
        },
        'candidates_table': evaluated,
        'shortlist': shortlist,
        'compliance_verdict': compliance_verdict,
        'bird_only_verdict': bird_only,
    }
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--continuity-report', default='')
    parser.add_argument('--offline-gate-report', default='')
    parser.add_argument('--shortlist-size', type=int, default=3)
    parser.add_argument('--out', required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    continuity = _read_json((args.continuity_report or '').strip() or None)
    offline = _read_json((args.offline_gate_report or '').strip() or None)

    report = build_detector_shortlist_report(
        continuity_report=continuity,
        offline_gate_report=offline,
        shortlist_size=max(1, int(args.shortlist_size)),
    )
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(out_path), 'schema': report['schema']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
