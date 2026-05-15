#!/usr/bin/env python3
# flake8: noqa
"""Run execution-level Re-ID checks for #389 and emit a single JSON report."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _bootstrap_imports(root: Path) -> None:
    if (root / 'web').is_dir() and (root / 'processor').is_dir():
        app_dir = root
        web_dir = root / 'web'
        proc_dir = root / 'processor' / 'src'
    else:
        app_dir = root / 'app'
        web_dir = root / 'app' / 'web'
        proc_dir = root / 'app' / 'processor' / 'src'
    scripts_dir = root / 'scripts'
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    if str(web_dir) not in sys.path:
        sys.path.insert(0, str(web_dir))
    if str(proc_dir) not in sys.path:
        sys.path.insert(0, str(proc_dir))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    os.environ.setdefault('FLASK_CREATE_APP_ON_IMPORT', '0')
    os.environ['BIRDLENSE_ENV'] = 'development'
    os.environ['FLASK_ENV'] = 'development'


def _resolve_verify_path(root: Path) -> Path:
    primary = root / 'scripts' / 'verify_reid_production_gates.py'
    if primary.is_file():
        return primary
    fallback = Path('/tmp/verify_reid_production_gates.py')
    if fallback.is_file():
        return fallback
    return primary


def _resolve_importer_path(root: Path) -> Path:
    primary = root / 'scripts' / 'reid' / 'import_embeddings_sqlite.py'
    if primary.is_file():
        return primary
    fallback = Path('/tmp/import_embeddings_sqlite.py')
    if fallback.is_file():
        return fallback
    return primary


def _load_verify_module(root: Path) -> Any:
    mod_path = _resolve_verify_path(root)
    spec = importlib.util.spec_from_file_location('verify_reid_production_gates', mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load verify module from {mod_path}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['verify_reid_production_gates'] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-json', required=True)
    p.add_argument('--window-hours', type=int, default=168)
    p.add_argument('--video-limit', type=int, default=300)
    p.add_argument('--min-embeddings', type=int, default=1)
    p.add_argument('--max-missing-contract-rows', type=int, default=0)
    p.add_argument('--max-stale-hours', type=float, default=8760.0)
    p.add_argument('--min-suggestion-count', type=int, default=0)
    return p.parse_args()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _importer_probe(root: Path, sample_row: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix='reid_import_probe_') as td:
        tmp = Path(td)
        probe_db = tmp / 'probe.db'
        probe_jsonl = tmp / 'probe.jsonl'
        valid = {
            'path': str(sample_row['crop_path']),
            'model': str(sample_row['model']),
            'dim': int(sample_row['dim']),
            'embedding': json.loads(sample_row['embedding_json']),
            'embedding_schema': str(sample_row.get('embedding_schema') or 'embedding_schema@v1'),
            'embedding_model_id': str(sample_row.get('embedding_model_id') or 'manual:probe'),
            'embedding_model_sha16': str(sample_row.get('embedding_model_sha16') or 'deadbeefcafebabe'),
            'crop_fingerprint_sha16': str(sample_row.get('crop_fingerprint_sha16') or 'feedfacecafebabe'),
            'created_at_utc': str(sample_row.get('jsonl_created_at_utc') or '2026-01-01T00:00:00Z'),
        }
        invalid = dict(valid)
        invalid.pop('embedding_schema', None)
        invalid.pop('embedding_model_id', None)
        probe_jsonl.write_text(
            json.dumps(valid, ensure_ascii=False) + '\n' + json.dumps(invalid, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )
        import_script = _resolve_importer_path(root)
        cmd = [
            'python3',
            str(import_script),
            '--db',
            str(probe_db),
            '--jsonl',
            str(probe_jsonl),
        ]
        run = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stderr = run.stderr.strip().splitlines()
        parsed: dict[str, Any] = {}
        for ln in reversed(stderr):
            try:
                parsed = json.loads(ln)
                if isinstance(parsed, dict):
                    break
            except Exception:
                continue
        return {
            'cmd': ' '.join(cmd),
            'exit_code': int(run.returncode),
            'rows_written': int(parsed.get('rows_written') or 0),
            'rows_skipped': int(parsed.get('rows_skipped') or 0),
            'stderr_tail': stderr[-5:],
        }


def main() -> int:
    args = _parse_args()
    out_path = Path(args.output_json).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    root_env = os.environ.get('BIRDLENSE_ROOT', '').strip()
    if root_env:
        root = Path(root_env).resolve()
    else:
        p = Path(__file__).resolve()
        root = p.parents[2] if len(p.parents) >= 3 else Path.cwd().resolve()
    _bootstrap_imports(root)
    verify_mod = _load_verify_module(root)

    from app import create_app
    from app_config.app_config import app_config
    from models import db, Video
    from services.ml_ops_service import build_reid_summary, build_video_reid_match_payload
    from util import ensure_utc

    app = create_app()
    cutoff = _utc_now() - timedelta(hours=max(1, int(args.window_hours)))

    report: dict[str, Any] = {
        'schema': 'reid_execution_report@v1',
        'ok': False,
        'window_hours': int(args.window_hours),
        'video_limit': int(args.video_limit),
    }

    with app.app_context():
        orig_mode = app_config.get('processor.reid_embedding_pipeline_mode')
        orig_kill = app_config.get('processor.reid_kill_switch')
        orig_shadow = app_config.get('processor.reid_shadow_mode')
        try:
            app_config.set('processor.reid_embedding_pipeline_mode', 'nearline')
            app_config.set('processor.reid_kill_switch', False)
            app_config.set('processor.reid_shadow_mode', False)

            summary, _ = build_reid_summary(db.session)
            summary_contract = summary.get('contract') if isinstance(summary.get('contract'), dict) else {}

            videos = (
                db.session.query(Video)
                .filter(Video.start_time >= cutoff.isoformat())
                .order_by(Video.start_time.desc(), Video.id.desc())
                .limit(max(1, int(args.video_limit)))
                .all()
            )
            video_ids = [int(v.id) for v in videos]

            sampled_matches: list[dict[str, Any]] = []
            for vid in video_ids:
                payload, status = build_video_reid_match_payload(db.session, vid)
                sampled_matches.append(
                    {
                        'video_id': int(vid),
                        'status': int(status),
                        'available': bool(payload.get('available')),
                        'contract_ready': bool(payload.get('contract_ready')),
                        'suggestions': len(payload.get('matches') or []),
                        'payload': payload,
                    }
                )

            probe = next((m for m in sampled_matches if m['suggestions'] > 0), None)
            if probe is None:
                probe = sampled_matches[0] if sampled_matches else None

            nearline_metrics = {
                'videos_evaluated': len(sampled_matches),
                'available_count': sum(1 for m in sampled_matches if m['available']),
                'contract_ready_count': sum(1 for m in sampled_matches if m['contract_ready']),
                'suggestions_total': sum(int(m['suggestions']) for m in sampled_matches),
            }

            probe_match = probe['payload'] if isinstance(probe, dict) and probe.get('payload') else None
            probe_video_id = int(probe['video_id']) if isinstance(probe, dict) and probe.get('video_id') is not None else None

            base_ok, base_gate = verify_mod.verify_reid_gates(
                reid_summary=summary,
                reid_match=probe_match,
                min_embeddings=int(args.min_embeddings),
                max_missing_contract_rows=int(args.max_missing_contract_rows),
                require_contract_ok=True,
                max_stale_hours=float(args.max_stale_hours),
                min_suggestion_count=int(args.min_suggestion_count),
            )

            schema_fail_summary = copy.deepcopy(summary)
            if not isinstance(schema_fail_summary.get('contract'), dict):
                schema_fail_summary['contract'] = {}
            schema_fail_summary['contract']['status'] = 'mixed_schema'
            schema_ok, schema_gate = verify_mod.verify_reid_gates(
                reid_summary=schema_fail_summary,
                reid_match=probe_match,
                min_embeddings=int(args.min_embeddings),
                max_missing_contract_rows=int(args.max_missing_contract_rows),
                require_contract_ok=True,
                max_stale_hours=float(args.max_stale_hours),
                min_suggestion_count=int(args.min_suggestion_count),
            )

            stale_fail_summary = copy.deepcopy(summary)
            if not isinstance(stale_fail_summary.get('contract'), dict):
                stale_fail_summary['contract'] = {}
            stale_fail_summary['contract']['max_embedding_age_hours'] = float(args.max_stale_hours) + 100.0
            stale_ok, stale_gate = verify_mod.verify_reid_gates(
                reid_summary=stale_fail_summary,
                reid_match=probe_match,
                min_embeddings=int(args.min_embeddings),
                max_missing_contract_rows=int(args.max_missing_contract_rows),
                require_contract_ok=True,
                max_stale_hours=float(args.max_stale_hours),
                min_suggestion_count=int(args.min_suggestion_count),
            )

            importer_probe = {'exit_code': 1, 'rows_written': 0, 'rows_skipped': 0, 'skipped': 'reid_embedding_missing'}
            has_reid = bool(
                db.session.execute(
                    db.text(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reid_embedding'"
                    )
                ).scalar()
            )
            if has_reid:
                sample_row = db.session.execute(
                    db.text(
                        'SELECT crop_path, model, dim, embedding_json, embedding_schema, '
                        'embedding_model_id, embedding_model_sha16, crop_fingerprint_sha16, '
                        'jsonl_created_at_utc '
                        'FROM reid_embedding WHERE embedding_json IS NOT NULL LIMIT 1'
                    )
                ).mappings().first()
                if sample_row is not None:
                    importer_probe = _importer_probe(root, dict(sample_row))

            missing_contract_rows = int(summary_contract.get('missing_contract_rows') or 0)
            embedding_count = int(summary.get('embedding_count') or 0)

            rollback_checks = {
                'probe_video_id': probe_video_id,
                'baseline_suggestions': len((probe_match or {}).get('matches') or []),
            }
            if probe_video_id is not None:
                app_config.set('processor.reid_kill_switch', True)
                app_config.set('processor.reid_shadow_mode', False)
                ks_payload, _ = build_video_reid_match_payload(db.session, probe_video_id)

                app_config.set('processor.reid_kill_switch', False)
                app_config.set('processor.reid_shadow_mode', True)
                sh_payload, _ = build_video_reid_match_payload(db.session, probe_video_id)

                rollback_checks.update(
                    {
                        'kill_switch_policy': bool((ks_payload.get('policy') or {}).get('kill_switch')),
                        'kill_switch_suggestions': len(ks_payload.get('matches') or []),
                        'shadow_mode_policy': bool((sh_payload.get('policy') or {}).get('shadow_mode')),
                        'shadow_mode_suggestions': len(sh_payload.get('matches') or []),
                    }
                )

            report.update(
                {
                    'nearline_shadow': nearline_metrics,
                    'base_gate': base_gate,
                    'import_metrics': {
                        'embedding_count': embedding_count,
                        'missing_contract_rows': missing_contract_rows,
                        'importer_probe': importer_probe,
                    },
                    'failover_checks': {
                        'schema_mismatch_triggered': (not schema_ok)
                        and any(
                            str(e).startswith('contract_status_not_ok')
                            for e in (schema_gate.get('errors') or [])
                        ),
                        'schema_gate': schema_gate,
                        'stale_triggered': (not stale_ok)
                        and any(
                            str(e).startswith('embedding_age_above_threshold')
                            for e in (stale_gate.get('errors') or [])
                        ),
                        'stale_gate': stale_gate,
                    },
                    'rollback_checks': rollback_checks,
                    'artifacts': {
                        'probe_video_id': probe_video_id,
                        'sampled_video_ids': video_ids[:20],
                    },
                }
            )

            report['ok'] = bool(base_ok) and bool(report['failover_checks']['schema_mismatch_triggered']) and bool(
                report['failover_checks']['stale_triggered']
            ) and int(importer_probe.get('rows_written') or 0) >= 1 and int(
                importer_probe.get('rows_skipped') or 0
            ) >= 1 and bool(
                rollback_checks.get('kill_switch_policy')
            ) and int(
                rollback_checks.get('kill_switch_suggestions') or 0
            ) == 0 and bool(
                rollback_checks.get('shadow_mode_policy')
            ) and int(
                rollback_checks.get('shadow_mode_suggestions') or 0
            ) == 0
        finally:
            app_config.set('processor.reid_embedding_pipeline_mode', orig_mode)
            app_config.set('processor.reid_kill_switch', orig_kill)
            app_config.set('processor.reid_shadow_mode', orig_shadow)

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': bool(report.get('ok')), 'output': str(out_path)}))
    return 0 if bool(report.get('ok')) else 1


if __name__ == '__main__':
    raise SystemExit(main())
