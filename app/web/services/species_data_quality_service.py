"""Аудит строк Species: дубликаты имён и чистота пользовательского каталога.

Блоклист объектов удалён: при включённом catalog_strict_ingest любые имена
вне allowlist автоматически идут в Unknown без отдельного списка.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import func

from app_config.app_config import app_config
from models import Species, SpeciesVisit
from services.species_catalog.allowlist import (
    load_catalog_allowlist_norm_keys,
    species_matches_allowlist,
)
from services.species_catalog.canon import (
    is_all_caps_display_name,
    is_hierarchy_taxon_label,
    normalize_catalog_display_name,
)
from species_constants import GENERIC_BIRD_SPECIES
from util import load_species_canonical_mapping


def _norm_key(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def find_duplicate_name_groups(
    session,
    limit_groups: int = 100,
    *,
    skip_inactive_empty_groups: bool = True,
) -> list[dict[str, Any]]:
    """Группы с одинаковым нормализованным именем (разный id) — риск слияния.

    skip_inactive_empty_groups: для отчёта качества скрыть группы, где все строки
    неактивны и без визитов (шум). Для reconcile — False, чтобы сливать и «пустые» дубликаты.
    """
    rows = (
        session.query(
            Species.id,
            Species.name,
            Species.active,
            func.count(SpeciesVisit.id).label("visit_count"),
        )
        .outerjoin(SpeciesVisit, SpeciesVisit.species_id == Species.id)
        .group_by(Species.id)
        .order_by(Species.id.asc())
        .all()
    )
    by_norm: dict[str, list[tuple[int, str, bool, int]]] = defaultdict(list)
    for sid, name, active, visit_count in rows:
        nk = _norm_key(name or "") or (name or "").strip().lower()
        by_norm[nk].append((int(sid), name or "", bool(active), int(visit_count or 0)))

    def _group_relevant(pairs: list[tuple[int, str, bool, int]]) -> bool:
        if skip_inactive_empty_groups:
            return any(active or visit_count > 0 for _sid, _name, active, visit_count in pairs)
        return True

    multi = [(nk, pairs) for nk, pairs in by_norm.items() if len(pairs) > 1 and _group_relevant(pairs)]
    multi.sort(key=lambda x: len(x[1]), reverse=True)
    out: list[dict[str, Any]] = []
    for nk, pairs in multi[:limit_groups]:
        out.append(
            {
                "normalized_name": nk,
                "count": len(pairs),
                "species": [{"id": i, "name": n} for i, n, _active, _visit_count in pairs],
            }
        )
    return out


def build_data_quality_report(
    session,
    *,
    duplicate_group_limit: int = 80,
) -> dict[str, Any]:
    """Сводка по каталогу: дубликаты имён, подсказки по merge и эндпоинтам качества."""
    dupes = find_duplicate_name_groups(session, limit_groups=duplicate_group_limit)
    total = session.query(func.count(Species.id)).scalar() or 0
    return {
        "species_total": total,
        "duplicate_name_group_count": len(dupes),
        "duplicate_name_groups": dupes,
        "hints": {
            "merge_duplicates_endpoint": "POST /api/ui/system/merge-duplicate-species",
            "per_video_merge": "POST /api/ui/videos/<id>/merge-species",
            "registry_health": "GET /api/ui/system/species-registry/health",
            "classifier_catalog_dataset_alignment": (
                "GET /api/ui/system/species-registry/classifier-dataset-alignment"
            ),
            "catalog_reconcile": "POST /api/ui/system/species-catalog/reconcile",
        },
    }


def species_ids_to_exclude_from_bird_catalog(session) -> frozenset[int]:
    """Return species IDs to hide in bird catalogs (service labels + optional off-allowlist)."""
    filter_off_allowlist = bool(
        app_config.get("species.catalog_filter_off_allowlist", False)
    )
    mapping = load_species_canonical_mapping()
    allow_keys = load_catalog_allowlist_norm_keys(app_config.get)
    service_names = {
        GENERIC_BIRD_SPECIES.strip().lower(),
        "unknown",
    }
    rows = (
        session.query(
            Species.id,
            Species.name,
            func.count(SpeciesVisit.id).label("visit_count"),
        )
        .outerjoin(SpeciesVisit, SpeciesVisit.species_id == Species.id)
        .group_by(Species.id)
        .all()
    )
    excluded: set[int] = set()
    for sid, name, visit_count in rows:
        clean_name = str(name or "").strip()
        if not clean_name:
            continue
        if clean_name.lower() in service_names:
            excluded.add(int(sid))
            continue
        if is_hierarchy_taxon_label(
            clean_name,
            allowlist_norm_keys=allow_keys,
            mapping=mapping,
        ):
            excluded.add(int(sid))
            continue
        if filter_off_allowlist:
            if int(visit_count or 0) <= 0:
                continue
            if not allow_keys:
                continue
            if not species_matches_allowlist(clean_name, allow_keys, mapping):
                excluded.add(int(sid))
    return frozenset(excluded)


def build_catalog_polish_report(session, *, limit: int = 2000) -> dict[str, Any]:
    """Сводка для глубокой полировки каталога: CAPS, таксон-узлы, неполные карточки."""
    mapping = load_species_canonical_mapping()
    allow_keys = load_catalog_allowlist_norm_keys(app_config.get)
    rows = session.query(Species.id, Species.name, Species.image_url, Species.description).all()
    caps_ids: list[int] = []
    taxon_ids: list[int] = []
    rename_candidates: list[dict[str, str]] = []
    missing_image = 0
    missing_description = 0
    for sid, name, image_url, description in rows:
        clean = str(name or "").strip()
        if not clean:
            continue
        if is_all_caps_display_name(clean):
            caps_ids.append(int(sid))
        if is_hierarchy_taxon_label(clean, allowlist_norm_keys=allow_keys, mapping=mapping):
            taxon_ids.append(int(sid))
        normalized = normalize_catalog_display_name(clean, mapping)
        if normalized and normalized != clean:
            rename_candidates.append({"id": str(sid), "from": clean, "to": normalized})
        if not str(image_url or "").strip():
            missing_image += 1
        if not str(description or "").strip():
            missing_description += 1
    return {
        "species_total": len(rows),
        "all_caps_count": len(caps_ids),
        "taxon_node_count": len(taxon_ids),
        "rename_candidate_count": len(rename_candidates),
        "missing_image_count": missing_image,
        "missing_description_count": missing_description,
        "rename_candidates_sample": rename_candidates[: min(limit, 40)],
        "all_caps_ids_sample": caps_ids[:20],
        "taxon_node_ids_sample": taxon_ids[:20],
    }
