"""Приведение каталога Species к allowlist Birder 707 + Rodent без legacy-мусора."""

from __future__ import annotations

from typing import Any

from models import Species, db
from services.legacy_import_cleanup_service import cleanup_legacy_import_placeholders
from services.species_catalog.allowlist import (
    load_catalog_allowlist_norm_keys,
    species_matches_allowlist,
    species_name_match_norm_keys,
)
from services.species_catalog.canon import (
    is_hierarchy_taxon_label,
    normalize_catalog_display_name,
)
from services.species_catalog.reconcile import (
    _has_child_species,
    _species_has_activity,
    _unknown_species,
    deep_reconcile_species_catalog,
    reconcile_species_catalog,
)
from services.species_merge_service import merge_species_into
from util import load_species_canonical_mapping


_PROTECTED_NAMES = frozenset({"bird", "birds", "unknown", "rodent", "squirrel"})


def _protected_ids() -> set[int]:
    out: set[int] = set()
    unknown = _unknown_species()
    if unknown:
        out.add(int(unknown.id))
    for name in ("Bird", "Birds", "Rodent", "Squirrel"):
        row = Species.query.filter_by(name=name).first()
        if row:
            out.add(int(row.id))
    return out


def _pick_collision_target(
    a: Species,
    b: Species,
    allow_keys: frozenset[str] | None,
    mapping: dict[str, str],
) -> tuple[Species, Species]:
    """Куда сливать: предпочтение allowlist, затем меньший id."""

    def score(sp: Species) -> tuple[int, int]:
        in_allow = 0
        if allow_keys and species_matches_allowlist(sp.name or "", allow_keys, mapping):
            in_allow = 1
        # Стабильный target: allowlist, затем меньший id (старее каноническая строка).
        return (in_allow, -int(sp.id or 0))

    return (a, b) if score(a) >= score(b) else (b, a)


def merge_canonical_name_collisions(
    *,
    dry_run: bool = True,
    limit: int = 2000,
    app_config_get=None,
) -> dict[str, Any]:
    """Слить строки, у которых каноническое имя совпадает с уже существующей Species."""
    if app_config_get is None:
        from app_config.app_config import app_config

        app_config_get = app_config.get

    mapping = load_species_canonical_mapping()
    allow_keys = load_catalog_allowlist_norm_keys(app_config_get)
    protected = _protected_ids()
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "merged": 0,
        "details": [],
        "errors": [],
    }
    cap = max(1, min(int(limit or 2000), 10000))
    groups: dict[str, list[Species]] = {}
    for sp in Species.query.order_by(Species.id.asc()).all():
        if int(sp.id) in protected:
            continue
        canon = normalize_catalog_display_name(sp.name or "", mapping)
        if not canon:
            continue
        key = canon.strip().lower()
        groups.setdefault(key, []).append(sp)

    for key, members in groups.items():
        if len(members) < 2:
            continue
        target = members[0]
        for other in members[1:]:
            target, source = _pick_collision_target(target, other, allow_keys, mapping)
        for source in members:
            if int(source.id) == int(target.id):
                continue
            canon = normalize_catalog_display_name(source.name or "", mapping) or key
            detail = (
                f"collision merge: {source.id} {source.name!r} → {target.id} {target.name!r} "
                f"(canon={canon!r})"
            )
            report["details"].append(detail)
            report["merged"] += 1
            if report["merged"] > cap:
                break
            if not dry_run:
                merge_species_into(int(source.id), int(target.id))
        if report["merged"] > cap:
            break

    if not dry_run:
        db.session.commit()
    else:
        db.session.rollback()
    return report


def merge_duplicate_allowlist_species(
    *,
    dry_run: bool = True,
    app_config_get=None,
) -> dict[str, Any]:
    """Одна строка Species на класс allowlist (слияние legacy-дублей с разными именами)."""
    if app_config_get is None:
        from app_config.app_config import app_config

        app_config_get = app_config.get

    mapping = load_species_canonical_mapping()
    allow_keys = load_catalog_allowlist_norm_keys(app_config_get)
    protected = _protected_ids()
    report: dict[str, Any] = {"dry_run": dry_run, "merged": 0, "details": []}
    if not allow_keys:
        report["errors"] = ["allowlist empty"]
        return report

    rows = Species.query.order_by(Species.id.asc()).all()
    by_key: dict[str, list[Species]] = {}
    for sp in rows:
        if int(sp.id) in protected:
            continue
        match_keys = species_name_match_norm_keys(sp.name or "", mapping) & allow_keys
        if not match_keys:
            continue
        canon_key = min(match_keys)
        by_key.setdefault(canon_key, []).append(sp)

    for canon_key, members in by_key.items():
        if len(members) < 2:
            continue
        target = members[0]
        for other in members[1:]:
            target, _ = _pick_collision_target(target, other, allow_keys, mapping)
        for source in members:
            if int(source.id) == int(target.id):
                continue
            report["details"].append(
                f"allowlist dedupe {canon_key!r}: {source.id} {source.name!r} → {target.id} {target.name!r}",
            )
            report["merged"] += 1
            if not dry_run:
                merge_species_into(int(source.id), int(target.id))

    if not dry_run:
        db.session.commit()
    else:
        db.session.rollback()
    return report


def purge_empty_hierarchy_nodes(*, dry_run: bool = True, app_config_get=None) -> dict[str, Any]:
    """Удалить узлы-группы иерархии без детей и без наблюдений."""
    if app_config_get is None:
        from app_config.app_config import app_config

        app_config_get = app_config.get

    mapping = load_species_canonical_mapping()
    allow_keys = load_catalog_allowlist_norm_keys(app_config_get)
    protected = _protected_ids()
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "deleted": 0,
        "skipped_has_children": 0,
        "skipped_has_activity": 0,
        "skipped_not_hierarchy": 0,
        "details": [],
    }
    for sp in Species.query.order_by(Species.id.asc()).all():
        if int(sp.id) in protected:
            continue
        name = str(sp.name or "").strip()
        if not name or name.strip().lower() in _PROTECTED_NAMES:
            continue
        if not is_hierarchy_taxon_label(name, allowlist_norm_keys=allow_keys, mapping=mapping):
            report["skipped_not_hierarchy"] += 1
            continue
        if _has_child_species(int(sp.id)):
            report["skipped_has_children"] += 1
            continue
        if _species_has_activity(int(sp.id)):
            report["skipped_has_activity"] += 1
            continue
        report["details"].append(f"delete empty hierarchy: {sp.id} {name!r}")
        report["deleted"] += 1
        if not dry_run:
            db.session.delete(sp)

    if not dry_run:
        db.session.commit()
    else:
        db.session.rollback()
    return report


def audit_species_catalog(app_config_get=None) -> dict[str, Any]:
    """Сводка: allowlist vs legacy, пустые, иерархия."""
    if app_config_get is None:
        from app_config.app_config import app_config

        app_config_get = app_config.get

    mapping = load_species_canonical_mapping()
    allow_keys = load_catalog_allowlist_norm_keys(app_config_get) or frozenset()
    total = 0
    on_allowlist = 0
    off_allowlist = 0
    off_empty = 0
    off_active = 0
    hierarchy = 0
    hierarchy_empty = 0
    for sp in Species.query.order_by(Species.id.asc()).all():
        total += 1
        name = str(sp.name or "").strip()
        if is_hierarchy_taxon_label(name, allowlist_norm_keys=allow_keys, mapping=mapping):
            hierarchy += 1
            if not _has_child_species(int(sp.id)) and not _species_has_activity(int(sp.id)):
                hierarchy_empty += 1
        if species_matches_allowlist(name, allow_keys, mapping):
            on_allowlist += 1
        else:
            off_allowlist += 1
            if _species_has_activity(int(sp.id)):
                off_active += 1
            else:
                off_empty += 1
    return {
        "species_total": total,
        "on_allowlist": on_allowlist,
        "off_allowlist": off_allowlist,
        "off_allowlist_empty": off_empty,
        "off_allowlist_active": off_active,
        "hierarchy_nodes": hierarchy,
        "hierarchy_empty": hierarchy_empty,
        "allowlist_norm_keys": len(allow_keys),
    }


def idealize_species_catalog(
    *,
    dry_run: bool = True,
    purge_legacy_placeholders: bool = True,
    reassign_active_off_allowlist: bool = True,
    app_config_get=None,
) -> dict[str, Any]:
    """Полный проход: deep reconcile → collision merge → purge legacy → materialize."""
    if app_config_get is None:
        from app_config.app_config import app_config

        app_config_get = app_config.get

    from services.species_catalog.registry import ensure_allowlist_species_materialized

    before = audit_species_catalog(app_config_get)
    legacy_vs = 0
    legacy_visits = 0
    if purge_legacy_placeholders and not dry_run:
        legacy_vs, legacy_visits = cleanup_legacy_import_placeholders()
        db.session.commit()

    deep = deep_reconcile_species_catalog(dry_run=dry_run, app_config_get=app_config_get)
    collisions = merge_canonical_name_collisions(dry_run=dry_run, app_config_get=app_config_get)
    allowlist_dedupe = merge_duplicate_allowlist_species(dry_run=dry_run, app_config_get=app_config_get)
    purge_legacy = reconcile_species_catalog(
        dry_run=dry_run,
        merge_normalized_duplicate_names=True,
        delete_empty_off_allowlist=True,
        reassign_off_allowlist_to_unknown=reassign_active_off_allowlist,
        reassign_suspects_to_unknown=reassign_active_off_allowlist,
        app_config_get=app_config_get,
    )
    hierarchy = purge_empty_hierarchy_nodes(dry_run=dry_run, app_config_get=app_config_get)
    materialize = ensure_allowlist_species_materialized(
        app_config_get,
        fill_metadata=False,
        dry_run=dry_run,
        limit=8000,
    )
    after = audit_species_catalog(app_config_get)
    return {
        "dry_run": dry_run,
        "before": before,
        "after": after,
        "legacy_placeholders_removed": {"video_species": legacy_vs, "visits": legacy_visits},
        "deep_reconcile": deep,
        "canonical_collisions": collisions,
        "allowlist_dedupe": allowlist_dedupe,
        "purge_legacy": purge_legacy,
        "hierarchy_purge": hierarchy,
        "materialize": materialize,
    }


__all__ = [
    "audit_species_catalog",
    "idealize_species_catalog",
    "merge_canonical_name_collisions",
    "merge_duplicate_allowlist_species",
    "purge_empty_hierarchy_nodes",
]
