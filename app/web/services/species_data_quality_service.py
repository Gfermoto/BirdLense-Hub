"""Аудит строк Species: посторонние объекты в каталоге, дубликаты имён.

Блоклист: app/web/seed/species_suspect_blocklist.txt (точное совпадение имени вида
или таксона; для однословных строк длины >= 5 — совпадение отдельного токена в имени).
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from functools import lru_cache
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


def _blocklist_path() -> str:
    return os.path.join(os.path.dirname(__file__), '..', 'seed', 'species_suspect_blocklist.txt')


@lru_cache(maxsize=1)
def _load_suspect_blocklist_sets() -> tuple[frozenset[str], frozenset[str]]:
    """exact phrases + single-word tokens (len>=5) for word-boundary-like checks."""
    exact: set[str] = set()
    token: set[str] = set()
    path = _blocklist_path()
    if not os.path.isfile(path):
        return frozenset(), frozenset()
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.split('#', 1)[0].strip()
            if not line:
                continue
            term = _norm_key(line)
            if not term:
                continue
            exact.add(term)
            if ' ' in term:
                continue
            if len(term) >= 5:
                token.add(term)
    return frozenset(exact), frozenset(token)


def suspect_reasons_for_species(
    species_name: str,
    taxon_common_name: str | None,
) -> list[str]:
    reasons: list[str] = []
    exact, tokens = _load_suspect_blocklist_sets()
    nk = _norm_key(species_name)
    tk = _norm_key(taxon_common_name or '')

    if nk in exact:
        reasons.append('species_name_blocklist')
    if tk and tk in exact:
        reasons.append('taxon_common_blocklist')
    for part in nk.split():
        if len(part) >= 5 and part in tokens:
            reasons.append('species_name_token_blocklist')
            break
    if tk:
        for part in tk.split():
            if len(part) >= 5 and part in tokens:
                if 'taxon_token_blocklist' not in reasons:
                    reasons.append('taxon_token_blocklist')
                break
    return reasons


def is_species_suspect_non_bird(sp: Species, taxon: SpeciesTaxon | None) -> bool:
    return bool(
        suspect_reasons_for_species(
            sp.name or '',
            taxon.common_name if taxon else None,
        )
    )


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
    suspect_limit: int = 500,
    duplicate_group_limit: int = 80,
) -> dict[str, Any]:
    exact, _tok = _load_suspect_blocklist_sets()
    blocklist_file = _blocklist_path()
    rows = (
        session.query(Species, SpeciesTaxon)
        .outerjoin(SpeciesTaxon, Species.taxon_id == SpeciesTaxon.id)
        .order_by(Species.id.asc())
        .all()
    )
    all_suspects: list[dict[str, Any]] = []
    visit_counts: dict[int, int] = {}
    vc_q = (
        session.query(
            SpeciesVisit.species_id,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0),
        )
        .group_by(SpeciesVisit.species_id)
    )
    for sid, total in vc_q.all():
        visit_counts[int(sid)] = int(total or 0)

    for sp, taxon in rows:
        reasons = suspect_reasons_for_species(sp.name or '', taxon.common_name if taxon else None)
        if not reasons:
            continue
        all_suspects.append({
            'id': sp.id,
            'name': sp.name,
            'parent_id': sp.parent_id,
            'taxon_id': sp.taxon_id,
            'taxon_common_name': taxon.common_name if taxon else None,
            'metadata_source': sp.metadata_source,
            'metadata_source_url': sp.metadata_source_url,
            'metadata_status': sp.metadata_status,
            'visit_weight': visit_counts.get(sp.id, 0),
            'reasons': reasons,
        })

    dupes = find_duplicate_name_groups(session, limit_groups=duplicate_group_limit)
    return {
        'species_total': session.query(func.count(Species.id)).scalar() or 0,
        'blocklist_entries': len(exact),
        'blocklist_file': blocklist_file,
        'suspect_count': len(all_suspects),
        'suspects': all_suspects[:suspect_limit],
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
    """Множество id для фильтра GET /species (exclude_suspects=1)."""
    rows = (
        session.query(Species, SpeciesTaxon)
        .outerjoin(SpeciesTaxon, Species.taxon_id == SpeciesTaxon.id)
        .all()
    )
    bad = {
        sp.id for sp, tx in rows
        if is_species_suspect_non_bird(sp, tx)
    }
    return frozenset(bad)
