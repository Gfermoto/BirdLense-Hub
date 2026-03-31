"""Аудит строк Species: дубликаты имён, выравнивание каталога с классификатором.

Блоклист объектов удалён: при включённом catalog_strict_ingest любые имена
вне allowlist автоматически идут в Unknown без отдельного списка.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import func

from models import Species, SpeciesTaxon, SpeciesVisit


def _norm_key(name: str) -> str:
    if not name:
        return ''
    s = name.strip().lower()
    s = s.replace('_', ' ').replace('-', ' ')
    s = re.sub(r'\s+', ' ', s)
    return s


def find_duplicate_name_groups(session, limit_groups: int = 100) -> list[dict[str, Any]]:
    """Группы с одинаковым нормализованным именем (разный id) — риск слияния."""
    rows = session.query(Species.id, Species.name).order_by(Species.id.asc()).all()
    by_norm: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for sid, name in rows:
        nk = _norm_key(name or '') or (name or '').strip().lower()
        by_norm[nk].append((int(sid), name or ''))
    multi = [(nk, pairs) for nk, pairs in by_norm.items() if len(pairs) > 1]
    multi.sort(key=lambda x: len(x[1]), reverse=True)
    out: list[dict[str, Any]] = []
    for nk, pairs in multi[:limit_groups]:
        out.append({
            'normalized_name': nk,
            'count': len(pairs),
            'species': [{'id': i, 'name': n} for i, n in pairs],
        })
    return out


def build_data_quality_report(
    session,
    *,
    duplicate_group_limit: int = 80,
) -> dict[str, Any]:
    dupes = find_duplicate_name_groups(session, limit_groups=duplicate_group_limit)
    total = session.query(func.count(Species.id)).scalar() or 0
    return {
        'species_total': total,
        'duplicate_name_group_count': len(dupes),
        'duplicate_name_groups': dupes,
        'hints': {
            'merge_duplicates_endpoint': 'POST /api/ui/system/merge-duplicate-species',
            'per_video_merge': 'POST /api/ui/videos/<id>/merge-species',
            'registry_health': 'GET /api/ui/system/species-registry/health',
            'classifier_catalog_dataset_alignment': (
                'GET /api/ui/system/species-registry/classifier-dataset-alignment'
            ),
            'catalog_reconcile': 'POST /api/ui/system/species-catalog/reconcile',
        },
    }


def species_ids_to_exclude_from_bird_catalog(session) -> frozenset[int]:
    """Множество id для фильтра GET /species (exclude_suspects=1).

    Blocklist удалён; возвращает пустое множество (все виды в каталоге чисты
    при catalog_strict_ingest=true + allowlist).
    Оставлен для обратной совместимости вызовов.
    """
    return frozenset()
