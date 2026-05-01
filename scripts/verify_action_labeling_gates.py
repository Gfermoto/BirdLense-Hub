#!/usr/bin/env python3
"""Verify action-labeling gates for #392."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CORE_LABELS = {'arrival', 'departure', 'possible_feeding'}
EXTENDED_LABELS = {'drinking', 'aggression', 'nesting_behavior'}


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path}: root must be object')
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding='utf-8').splitlines():
        if not ln.strip():
            continue
        obj = json.loads(ln)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def verify_action_gates(
    *,
    action_events: dict[str, Any] | None,
    dataset_rows: list[dict[str, Any]] | None,
    min_events: int,
    min_dataset_rows: int,
    min_segment_ms: int,
    allow_extended_labels: bool,
) -> tuple[bool, dict[str, Any]]:
    """Validate action-events payload and/or dataset JSONL rows."""
    errors: list[str] = []
    checks: dict[str, Any] = {}
    label_set = set(CORE_LABELS)
    if allow_extended_labels:
        label_set |= set(EXTENDED_LABELS)

    if action_events is not None:
        schema = action_events.get('schema')
        checks['action_events_schema'] = schema
        if schema != 'video_action_events@v1':
            errors.append('bad_action_events_schema')

        available = bool(action_events.get('available'))
        checks['action_events_available'] = available
        if not available:
            errors.append('action_events_not_available')

        events = action_events.get('events')
        if not isinstance(events, list):
            errors.append('action_events_not_list')
            events = []
        checks['action_events_count'] = len(events)
        checks['min_events'] = int(min_events)
        if len(events) < int(min_events):
            errors.append(
                'action_events_count_below_threshold:'
                f'{len(events)}<{int(min_events)}'
            )

        invalid_events = 0
        for ev in events:
            if not isinstance(ev, dict):
                invalid_events += 1
                continue
            label = str(ev.get('label') or '')
            if label not in label_set:
                invalid_events += 1
            try:
                confidence = float(ev.get('confidence'))
            except Exception:
                invalid_events += 1
                continue
            if confidence < 0.0 or confidence > 1.0:
                invalid_events += 1
            try:
                t_off = float(ev.get('time_offset'))
            except Exception:
                invalid_events += 1
                continue
            if t_off < 0.0:
                invalid_events += 1
        checks['action_events_invalid_rows'] = invalid_events
        if invalid_events > 0:
            errors.append(f'invalid_action_events_rows:{invalid_events}')

    if dataset_rows is not None:
        checks['dataset_rows'] = len(dataset_rows)
        checks['min_dataset_rows'] = int(min_dataset_rows)
        if len(dataset_rows) < int(min_dataset_rows):
            errors.append(
                'dataset_rows_below_threshold:'
                f'{len(dataset_rows)}<{int(min_dataset_rows)}'
            )

        req = {
            'video_id',
            'track_id',
            'camera_id',
            'action_label',
            't_start_ms',
            't_end_ms',
            'confidence',
            'annotator_id',
            'created_at_utc',
        }
        invalid_rows = 0
        for row in dataset_rows:
            if not isinstance(row, dict):
                invalid_rows += 1
                continue
            if not req.issubset(row.keys()):
                invalid_rows += 1
                continue
            label = str(row.get('action_label') or '')
            if label not in label_set:
                invalid_rows += 1
            try:
                t_start = int(row.get('t_start_ms'))
                t_end = int(row.get('t_end_ms'))
                conf = float(row.get('confidence'))
            except Exception:
                invalid_rows += 1
                continue
            if conf < 0.0 or conf > 1.0:
                invalid_rows += 1
            if t_end <= t_start:
                invalid_rows += 1
            if (t_end - t_start) < int(min_segment_ms):
                invalid_rows += 1
        checks['dataset_invalid_rows'] = invalid_rows
        checks['min_segment_ms'] = int(min_segment_ms)
        if invalid_rows > 0:
            errors.append(f'invalid_action_dataset_rows:{invalid_rows}')

    if action_events is None and dataset_rows is None:
        errors.append('no_inputs_provided')

    ok = len(errors) == 0
    out = {
        'schema': 'action_labeling_gates@v1',
        'ok': ok,
        'checks': checks,
        'errors': errors,
    }
    return ok, out


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--action-events',
        default='',
        help='JSON payload from /api/ui/videos/{video_id}/action-events',
    )
    parser.add_argument(
        '--dataset-jsonl',
        default='',
        help='JSONL labeled action dataset',
    )
    parser.add_argument('--min-events', type=int, default=1)
    parser.add_argument('--min-dataset-rows', type=int, default=1)
    parser.add_argument('--min-segment-ms', type=int, default=300)
    parser.add_argument('--allow-extended-labels', action='store_true')
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    if str(args.action_events).strip():
        action_events = _load_json(Path(args.action_events).resolve())
    else:
        action_events = None
    if str(args.dataset_jsonl).strip():
        dataset_rows = _read_jsonl(Path(args.dataset_jsonl).resolve())
    else:
        dataset_rows = None
    ok, out = verify_action_gates(
        action_events=action_events,
        dataset_rows=dataset_rows,
        min_events=int(args.min_events),
        min_dataset_rows=int(args.min_dataset_rows),
        min_segment_ms=int(args.min_segment_ms),
        allow_extended_labels=bool(args.allow_extended_labels),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
