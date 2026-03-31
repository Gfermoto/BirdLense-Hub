"""Согласованность каталога видов, классов YOLO-классификатора и папок датасета Hub.

Имена классов читаются из весов (как ``TwoStageStrategy._normalize_class_name`` в процессоре).
Папки датасета — как ``dataset_export_service._sanitize_dirname`` (имена видов в БД).
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

from sqlalchemy import func

from models import Species, VideoSpecies
from services.species_catalog_allowlist_service import load_catalog_allowlist_names
from services.dataset_export_service import _sanitize_dirname
from util import data_dir, load_species_canonical_mapping, normalize_species_to_canonical


def _norm_key(name: str) -> str:
    if not name:
        return ''
    s = name.strip().lower()
    s = s.replace('_', ' ').replace('-', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s


def normalize_classifier_label(name: str) -> str:
    """Синхронно с ``app/processor/src/detection_strategy.TwoStageStrategy._normalize_class_name``."""
    return str(name).replace('_OR_', '/').replace('_', ' ')


def _processor_root() -> str:
    """Каталог ``app/processor`` (рядом с ``app/web``)."""
    web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.abspath(os.path.join(web_dir, '..', 'processor'))


def resolve_classifier_weights_path(app_config_get) -> tuple[str, str]:
    """
    Путь к весам классификатора как у процессора.
    Возвращает (абсолютный_путь, путь_для_логов).
    """
    rel = app_config_get('processor.models.classifier', 'models/classification/weights/best.pt')
    rel = rel or 'models/classification/weights/best.pt'
    if os.path.isabs(rel):
        return rel, rel
    abs_path = os.path.join(_processor_root(), rel)
    return abs_path, rel


@lru_cache(maxsize=8)
def _load_yolo_classify_names(weights_path: str) -> tuple[str, ...]:
    from ultralytics import YOLO

    model = YOLO(weights_path, task='classify')
    names = model.names
    if isinstance(names, dict):
        def _key_order(k):
            try:
                return int(k)
            except (TypeError, ValueError):
                return k

        return tuple(str(names[k]) for k in sorted(names.keys(), key=_key_order))
    return tuple(str(x) for x in names)


def load_classifier_labels_or_error(weights_path: str) -> tuple[list[str] | None, str | None]:
    """
    Список сырых имён классов из checkpoint или (None, сообщение_об_ошибке).
    """
    if not os.path.isfile(weights_path):
        return None, f'classifier weights not found: {weights_path}'
    try:
        raw = _load_yolo_classify_names(weights_path)
    except ImportError as e:
        return None, f'ultralytics not available: {e}'
    except Exception as e:
        return None, f'failed to read classifier classes: {e}'
    return list(raw), None


def _species_name_match_keys(name: str, mapping: dict[str, str]) -> set[str]:
    """Набор нормализованных ключей для сопоставления с выходом классификатора."""
    keys: set[str] = set()
    if not name or not str(name).strip():
        return keys
    stripped = str(name).strip()
    keys.add(_norm_key(stripped))
    canon = normalize_species_to_canonical(stripped, mapping)
    keys.add(_norm_key(canon))
    m = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', stripped)
    if m:
        keys.add(_norm_key(m.group(1).strip()))
        keys.add(_norm_key(m.group(2).strip()))
    return {k for k in keys if k}


def _normalized_classifier_labels(raw_labels: list[str]) -> list[tuple[str, str]]:
    """Пары (сырое_имя_в_весах, нормализованный ключ).

    Для меток в формате "Scientific (Common)" добавляем и common-key, чтобы
    виды в БД, хранящиеся как "Eurasian Blue Tit", считались совпадающими.
    """
    out: list[tuple[str, str]] = []
    sci_common_re = re.compile(r'^(.+?)\s*\(([^)]+)\)\s*$')
    for raw in raw_labels:
        disp = normalize_classifier_label(raw).strip()
        nk = _norm_key(disp)
        if nk:
            out.append((raw, nk))
        m = sci_common_re.match(disp)
        if m:
            common_nk = _norm_key(m.group(2).strip())
            if common_nk:
                out.append((raw, common_nk))
    return out


def _species_ids_with_video_detections(session) -> set[int]:
    rows = session.query(VideoSpecies.species_id).distinct().all()
    return {int(r[0]) for r in rows if r[0] is not None}


def _dataset_split_class_names() -> set[str]:
    base = os.path.join(data_dir(), 'dataset')
    names: set[str] = set()
    for split in ('train', 'val'):
        root = os.path.join(base, split)
        if not os.path.isdir(root):
            continue
        try:
            for entry in os.listdir(root):
                if os.path.isdir(os.path.join(root, entry)):
                    names.add(entry)
        except OSError:
            continue
    return names


def build_classifier_dataset_alignment_report(
    session,
    app_config_get,
    *,
    classifier_limit: int = 600,
    catalog_limit: int = 400,
    dataset_limit: int = 200,
) -> dict[str, Any]:
    """
    Сводка рассогласований: классификатор ↔ Species ↔ папки ``data/dataset/{train,val}/*``.
    """
    mapping = load_species_canonical_mapping()
    abs_weights, log_weights = resolve_classifier_weights_path(app_config_get)
    raw_labels, err = load_classifier_labels_or_error(abs_weights)
    classifier_limit = max(50, min(classifier_limit, 5000))
    catalog_limit = max(50, min(catalog_limit, 5000))
    dataset_limit = max(50, min(dataset_limit, 2000))

    report: dict[str, Any] = {
        'classifier_weights_path': log_weights,
        'classifier_weights_resolved': abs_weights,
        'classifier_readable': raw_labels is not None,
        'classifier_error': err,
        'classifier_class_count': len(raw_labels) if raw_labels else 0,
        'hints': {
            'merge_duplicates': 'POST /api/ui/system/merge-duplicate-species',
            'canonical_mapping_file': 'app/web/seed/species_canonical_mapping.txt',
            'dataset_format': 'docs/DATASETS.md — Scientific (Common), YOLO cls folders',
        },
    }

    if not raw_labels:
        return report

    norm_pairs = _normalized_classifier_labels(raw_labels)
    label_norms = {nk for _raw, nk in norm_pairs}

    # species_id -> match keys
    species_rows = session.query(Species.id, Species.name).order_by(Species.id.asc()).all()
    sp_keys: dict[int, set[str]] = {}
    sanitize_to_species: dict[str, list[tuple[int, str]]] = {}
    for sid, name in species_rows:
        keys = _species_name_match_keys(name or '', mapping)
        sp_keys[int(sid)] = keys
        sd = _sanitize_dirname(name or '')
        sanitize_to_species.setdefault(sd, []).append((int(sid), name or ''))

    def species_matches_classifier(sid: int) -> bool:
        return bool(sp_keys.get(sid, set()) & label_norms)

    clf_unmatched_labels: list[str] = []
    for raw, nk in norm_pairs:
        if not nk:
            continue
        matched = any(nk in keys for keys in sp_keys.values())
        if not matched:
            clf_unmatched_labels.append(normalize_classifier_label(raw))
    clf_unmatched_full = sorted(set(clf_unmatched_labels))

    active_ids = _species_ids_with_video_detections(session)
    cat_unmatched_full: list[dict[str, Any]] = []
    for sid, name in species_rows:
        if sid not in active_ids:
            continue
        if species_matches_classifier(sid):
            continue
        cat_unmatched_full.append({'id': int(sid), 'name': name})

    dataset_names = _dataset_split_class_names()
    folder_orphans: list[str] = []
    folder_without_classifier: list[dict[str, Any]] = []
    for folder in sorted(dataset_names):
        species_list = sanitize_to_species.get(folder)
        if not species_list:
            folder_orphans.append(folder)
            continue
        for sid, sp_name in species_list:
            if not species_matches_classifier(sid):
                folder_without_classifier.append({
                    'folder': folder,
                    'species_id': sid,
                    'species_name': sp_name,
                })
                break

    report.update({
        'in_classifier_not_in_catalog': clf_unmatched_full[:classifier_limit],
        'in_classifier_not_in_catalog_count': len(clf_unmatched_full),
        'in_catalog_not_in_classifier': cat_unmatched_full[:catalog_limit],
        'in_catalog_not_in_classifier_count': len(cat_unmatched_full),
        'dataset_folder_count': len(dataset_names),
        'dataset_folders_without_catalog_match': folder_orphans[:dataset_limit],
        'dataset_folders_without_catalog_match_count': len(folder_orphans),
        'dataset_folders_species_not_in_classifier': folder_without_classifier[:dataset_limit],
        'dataset_folders_species_not_in_classifier_count': len(folder_without_classifier),
        'species_with_video_detections': len(active_ids),
        'catalog_species_total': session.query(func.count(Species.id)).scalar() or 0,
        'catalog_classifier_dataset_aligned': (
            len(clf_unmatched_full) == 0
            and len(cat_unmatched_full) == 0
            and len(folder_orphans) == 0
            and len(folder_without_classifier) == 0
        ),
    })
    return report


def build_catalog_coverage_metrics(session, app_config_get) -> dict[str, Any]:
    """Coverage metrics for catalog segments: observed / dataset / full EU."""
    allowlist_names = load_catalog_allowlist_names(app_config_get) or ()
    full_eu_count = len(allowlist_names)

    species_rows = session.query(Species.id, Species.name).order_by(Species.id.asc()).all()
    mapping = load_species_canonical_mapping()
    sp_keys: dict[int, set[str]] = {}
    sanitize_to_species: dict[str, set[int]] = {}
    for sid, name in species_rows:
        keys = _species_name_match_keys(name or '', mapping)
        sp_keys[int(sid)] = keys
        sanitize_to_species.setdefault(_sanitize_dirname(name or ''), set()).add(int(sid))

    # observed species (exclude generic placeholders)
    observed_ids = _species_ids_with_video_detections(session)
    service_names = {'bird', 'unknown'}
    observed_ids = {
        sid for sid in observed_ids
        if (session.query(Species.name).filter(Species.id == sid).scalar() or '').strip().lower() not in service_names
    }

    dataset_folders = _dataset_split_class_names()
    dataset_species_ids: set[int] = set()
    for folder in dataset_folders:
        for sid in sanitize_to_species.get(folder, set()):
            dataset_species_ids.add(sid)

    # observed that are part of full EU allowlist (by name match keys)
    allow_keys = {nk for name in allowlist_names for nk in _species_name_match_keys(name, mapping)}
    observed_in_full_eu = {sid for sid in observed_ids if sp_keys.get(sid, set()) & allow_keys}
    dataset_in_full_eu = {sid for sid in dataset_species_ids if sp_keys.get(sid, set()) & allow_keys}

    def _pct(a: int, b: int) -> float:
        return round((a / b) * 100.0, 2) if b else 0.0

    return {
        'observed_species_count': len(observed_ids),
        'dataset_species_count': len(dataset_species_ids),
        'full_eu_species_count': full_eu_count,
        'observed_in_full_eu_count': len(observed_in_full_eu),
        'dataset_in_full_eu_count': len(dataset_in_full_eu),
        'observed_vs_full_eu_percent': _pct(len(observed_in_full_eu), full_eu_count),
        'dataset_vs_full_eu_percent': _pct(len(dataset_in_full_eu), full_eu_count),
        'observed_in_dataset_count': len(observed_ids & dataset_species_ids),
        'observed_in_dataset_percent': _pct(len(observed_ids & dataset_species_ids), len(observed_ids)),
    }
