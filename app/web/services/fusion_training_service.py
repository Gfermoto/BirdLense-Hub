"""
Экспорт и оценка CSV для fusion-модели (decision_trace / VideoSpecies).

Вынесено из ui_system_routes (#265 фаза B).
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from data_paths import data_dir
from models import ActivityLog, VideoSpecies, db


def repo_root() -> Path:
    """Найти корень репо по наличию scripts/export_fusion_training_data.py."""
    current = Path(__file__).resolve()
    candidates: list[Path] = []
    candidates.extend(current.parents)
    candidates.append(Path.cwd().resolve())
    candidates.append(Path('/workspace'))
    candidates.append(Path('/app'))
    candidates.append(Path('/home/gfer/BirdLense'))
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        script = candidate / 'scripts' / 'export_fusion_training_data.py'
        if script.exists():
            return candidate
    msg = (
        'Could not locate repository root with '
        'scripts/export_fusion_training_data.py. '
        'Check the container layout and ensure the scripts directory is shipped.'
    )
    raise RuntimeError(msg)


def fusion_export_dir() -> Path:
    """Каталог data/exports/fusion."""
    out_dir = Path(data_dir()) / 'exports' / 'fusion'
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def latest_fusion_export_path() -> Path | None:
    """Последний fusion_training_*.csv по mtime."""
    out_dir = fusion_export_dir()
    candidates = sorted(
        out_dir.glob('fusion_training_*.csv'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def fusion_processor_src_dir() -> Path:
    """Каталог processor/src с fusion_metrics и fusion_model."""
    current = Path(__file__).resolve()
    candidates: list[Path] = []
    candidates.extend(current.parents)
    candidates.append(Path.cwd().resolve())
    candidates.append(Path('/app'))
    candidates.append(Path('/workspace'))
    candidates.append(Path('/home/gfer/BirdLense'))
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        src = candidate / 'processor' / 'src'
        fm = src / 'fusion_metrics.py'
        fmodel = src / 'fusion_model.py'
        if fm.exists() and fmodel.exists():
            return src
    raise RuntimeError(
        'Could not locate processor/src with fusion_metrics.py and fusion_model.py.',
    )


def ensure_fusion_processor_src_on_path() -> None:
    """Добавить processor/src в sys.path для импорта fusion_*."""
    src = fusion_processor_src_dir()
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def normalize_fusion_trace_row(row: dict) -> dict:
    """Привести строку трассы к полям CSV экспорта."""
    accepted = bool(row.get('accepted'))
    default_kind = 'accepted_species' if accepted else 'rejected'
    decision_kind = str(row.get('decision_kind') or default_kind)
    label = 1 if accepted else 0
    top1 = decision_kind == 'accepted_species'
    species_top1_label = 1 if accepted and top1 else 0
    dc = row.get('detector_conf')
    dc = dc or row.get('detector_confidence') or row.get('confidence') or 0.0
    cc = row.get('classifier_conf')
    cc = cc or row.get('classifier_confidence') or row.get('confidence') or 0.0
    bn = row.get('birdnet_prior') or row.get('_birdnet_prior') or 0.0
    kfs = row.get('key_frame_score') or row.get('best_frame_score') or 0.0
    mcc = row.get('multi_camera_count') or row.get('_multi_camera_count') or 0
    return {
        'detector_conf': dc,
        'classifier_conf': cc,
        'birdnet_prior': bn,
        'key_frame_score': kfs,
        'key_frame_count': row.get('key_frame_count') or 0,
        'multi_camera_count': mcc,
        'label': label,
        'valid_track_label': label,
        'species_top1_label': species_top1_label,
        'accepted': accepted,
        'decision_kind': decision_kind,
        'trust_band': row.get('trust_band') or ('green' if accepted else 'red'),
        'reject_reason_code': row.get('reject_reason_code') or '',
        'evidence_state': row.get('evidence_state') or '',
        'audio_evidence': row.get('audio_evidence') or 'none',
        'audio_support_count': row.get('audio_support_count') or 0,
        'audio_support_species': row.get('audio_support_species') or '',
        'audio_conflict_species': row.get('audio_conflict_species') or '',
        'audio_conflict_score': row.get('audio_conflict_score') or 0.0,
        'classifier_vote_share': row.get('classifier_vote_share') or 0.0,
        'track_id': row.get('track_id') or 0,
        'video_id': row.get('video_id') or 0,
        'species_name': row.get('species_name') or row.get('species') or '',
    }


def score_fusion_rows(
    rows: list[dict],
    model_path: str | None,
    score_col: str | None,
) -> list[dict]:
    """Добавить колонку score (модель или готовая колонка)."""
    ensure_fusion_processor_src_on_path()
    from fusion_model import FusionScorer  # type: ignore

    if score_col:
        scored = []
        for row in rows:
            out = dict(row)
            out['score'] = row.get(score_col)
            scored.append(out)
        return scored

    scorer = FusionScorer(model_path=model_path)
    scored = []
    for row in rows:
        det = row.get('detector_conf') or row.get('detector_confidence') or 0.0
        clf = row.get('classifier_conf') or row.get('classifier_confidence') or 0.0
        bnp = row.get('birdnet_prior') or row.get('_birdnet_prior') or 0.0
        kfs = row.get('key_frame_score') or row.get('best_frame_score') or 0.0
        kfc = float(row.get('key_frame_count') or 0.0)
        mcc = row.get('multi_camera_count') or row.get('_multi_camera_count') or 0.0
        features = {
            'detector_conf': det,
            'classifier_conf': clf,
            'birdnet_prior': bnp,
            'key_frame_score': kfs,
            'key_frame_count': kfc,
            'multi_camera_count': float(mcc),
        }
        out = dict(row)
        out['score'] = scorer.score(features)
        scored.append(out)
    return scored


def run_fusion_export_job() -> dict:
    """Записать CSV: сначала decision_trace, иначе VideoSpecies."""
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    out_path = fusion_export_dir() / f'fusion_training_{ts}.csv'
    ensure_fusion_processor_src_on_path()

    with out_path.open('w', encoding='utf-8', newline='') as fout:
        writer = csv.DictWriter(fout, fieldnames=[
            'detector_conf',
            'classifier_conf',
            'birdnet_prior',
            'key_frame_score',
            'key_frame_count',
            'multi_camera_count',
            'label',
            'valid_track_label',
            'species_top1_label',
            'accepted',
            'decision_kind',
            'trust_band',
            'reject_reason_code',
            'evidence_state',
            'audio_evidence',
            'audio_support_count',
            'audio_support_species',
            'audio_conflict_species',
            'audio_conflict_score',
            'classifier_vote_share',
            'track_id',
            'video_id',
            'species_name',
        ])
        writer.writeheader()

        trace_rows = (
            db.session.query(ActivityLog)
            .filter(ActivityLog.type == 'decision_trace')
            .order_by(ActivityLog.created_at.asc())
            .all()
        )
        written = 0
        if trace_rows:
            for trace in trace_rows:
                try:
                    payload = json.loads(trace.data or '{}')
                except (TypeError, ValueError):
                    continue
                for section_name in ('accepted_tracks', 'rejected_tracks'):
                    for row in payload.get(section_name) or []:
                        writer.writerow(normalize_fusion_trace_row(row))
                        written += 1
            return {
                'output_path': str(out_path),
                'rows_written': written,
                'source': 'decision_trace',
            }

        rows = (
            db.session.query(VideoSpecies)
            .filter(VideoSpecies.source == 'video')
            .all()
        )
        if not rows:
            raise RuntimeError(
                'No rows found in ActivityLog or VideoSpecies. Nothing exported.',
            )

        for r in rows:
            extra = {}
            raw_extra = getattr(r, 'extra', None)
            if raw_extra:
                try:
                    if isinstance(raw_extra, str):
                        extra = json.loads(raw_extra)
                    else:
                        extra = dict(raw_extra)
                except Exception:
                    extra = {}
            det_c = extra.get('detector_confidence') or getattr(r, 'confidence', 0.0)
            clf_c = extra.get('classifier_confidence') or getattr(r, 'confidence', 0.0)
            writer.writerow(
                normalize_fusion_trace_row(
                    {
                        'accepted': getattr(r, 'manually_corrected', False),
                        'decision_kind': (
                            'accepted_species'
                            if getattr(r, 'manually_corrected', False)
                            else 'accepted_generic'
                        ),
                        'species_name': getattr(
                            getattr(r, 'species', None), 'name', None,
                        ),
                        'track_id': getattr(r, 'track_id', None),
                        'video_id': getattr(r, 'video_id', None),
                        'detector_confidence': det_c,
                        'classifier_confidence': clf_c,
                        '_birdnet_prior': extra.get('_birdnet_prior') or 0.0,
                        'best_frame_score': extra.get('best_frame_score') or 0.0,
                        'key_frame_count': extra.get('key_frame_count') or 0,
                        '_multi_camera_count': extra.get('_multi_camera_count') or 0,
                    }
                )
            )
            written += 1
        return {
            'output_path': str(out_path),
            'rows_written': written,
            'source': 'video_species_fallback',
        }


def run_fusion_eval_job(
    source_csv: str | None = None,
    model_path: str | None = None,
    score_col: str | None = None,
    label_col: str = 'valid_track_label',
    slice_fields: list[str] | None = None,
) -> dict:
    """Метрики по CSV экспорта (и опционально по срезам)."""
    csv_path = Path(source_csv) if source_csv else latest_fusion_export_path()
    if not csv_path or not csv_path.exists():
        raise RuntimeError('Fusion export CSV not found. Run export first.')
    ensure_fusion_processor_src_on_path()
    from fusion_metrics import (  # type: ignore
        evaluate_binary_scores,
        evaluate_by_slice,
    )

    with csv_path.open('r', encoding='utf-8') as f:
        rows = [dict(row) for row in csv.DictReader(f)]
    if not rows:
        raise RuntimeError(f'No rows found in {csv_path}')

    thresholds = (0.5, 0.7, 0.8, 0.9, 0.95)
    scored = score_fusion_rows(rows, model_path, score_col)
    report = evaluate_binary_scores(
        scored,
        score_key='score',
        label_key=label_col,
        n_bins=10,
        thresholds=thresholds,
    )
    if slice_fields:
        report['slices'] = {
            field: evaluate_by_slice(
                scored,
                score_key='score',
                label_key=label_col,
                slice_field=field,
            )
            for field in slice_fields
            if field
        }
    return report
