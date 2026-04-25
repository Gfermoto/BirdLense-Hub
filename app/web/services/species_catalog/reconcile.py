"""Операции приведения каталога видов: дубликаты по имени, мусор, вне allowlist.

Реализация в ``services/species_catalog/``; shim —
``services/species_catalog_reconcile_service.py`` (#344).
"""

from __future__ import annotations

from typing import Any

from models import Species, SpeciesVisit, VideoSpecies, db
from services.species_catalog.allowlist import (
    load_catalog_allowlist_norm_keys,
    species_matches_allowlist,
)
from services.species_data_quality_service import find_duplicate_name_groups
from services.species_merge_service import merge_species_into
from util import load_species_canonical_mapping


def _unknown_species() -> Species | None:
    return Species.query.filter_by(name="Unknown").first()


def _species_has_activity(species_id: int) -> bool:
    if VideoSpecies.query.filter_by(species_id=species_id).first():
        return True
    if SpeciesVisit.query.filter_by(species_id=species_id).first():
        return True
    return False


def _has_child_species(species_id: int) -> bool:
    return Species.query.filter_by(parent_id=species_id).first() is not None


def _pick_merge_target(
    pairs: list[dict[str, Any]],
    allow_keys: frozenset[str] | None,
    mapping: dict[str, str],
) -> dict[str, Any]:
    """Выбрать строку, в которую сливаем остальные (предпочтение: имя из allowlist, затем короче, затем меньший id)."""

    def sort_key(p: dict[str, Any]) -> tuple:
        name = p.get("name") or ""
        in_allow = 0
        if allow_keys:
            in_allow = 0 if species_matches_allowlist(name, allow_keys, mapping) else 1
        return (in_allow, len(name), int(p["id"]))

    return min(pairs, key=sort_key)


def reconcile_species_catalog(
    *,
    dry_run: bool = True,
    merge_normalized_duplicate_names: bool = True,
    reassign_suspects_to_unknown: bool = False,
    reassign_off_allowlist_to_unknown: bool = False,
    delete_empty_suspects: bool = False,
    delete_empty_off_allowlist: bool = False,
    duplicate_group_limit: int = 500,
    app_config_get=None,
) -> dict[str, Any]:
    """
    merge_normalized_duplicate_names: одна строка Species на нормализованное имя.

    reassign_suspects_to_unknown: сохранён для обратной совместимости API; при включённом
        allowlist эквивалентен reassign_off_allowlist_to_unknown (все виды вне allowlist = suspects).
        delete_empty_suspects: без активности → удалить строку.

    reassign_off_allowlist_to_unknown: нет в species.catalog_allowlist_file (нужен файл);
        delete_empty_off_allowlist: без активности → удалить.
    """
    if app_config_get is None:
        from app_config.app_config import app_config

        app_config_get = app_config.get

    report: dict[str, Any] = {
        "dry_run": dry_run,
        "merged_duplicate_groups": 0,
        "merged_species_rows": 0,
        "suspects_reassigned": 0,
        "suspects_deleted_empty": 0,
        "off_allowlist_reassigned": 0,
        "off_allowlist_deleted_empty": 0,
        "errors": [],
        "details": [],
    }
    mapping = load_species_canonical_mapping()
    allow_keys = load_catalog_allowlist_norm_keys(app_config_get)
    unknown = _unknown_species()
    if (reassign_suspects_to_unknown or reassign_off_allowlist_to_unknown) and not unknown:
        report["errors"].append(
            "Species «Unknown» отсутствует — создайте вручную или через сид перед переносом.",
        )
        reassign_suspects_to_unknown = False
        reassign_off_allowlist_to_unknown = False

    protected_ids = {unknown.id} if unknown else set()
    for pname in ("Bird", "Birds"):
        row = Species.query.filter_by(name=pname).first()
        if row:
            protected_ids.add(row.id)

    # 1) Дубликаты по нормализованному имени
    if merge_normalized_duplicate_names:
        groups = find_duplicate_name_groups(
            db.session,
            limit_groups=duplicate_group_limit,
            skip_inactive_empty_groups=False,
        )
        for g in groups:
            pairs = g.get("species") or []
            if len(pairs) < 2:
                continue
            report["merged_duplicate_groups"] += 1
            target = _pick_merge_target(pairs, allow_keys, mapping)
            tid = int(target["id"])
            for other in pairs:
                oid = int(other["id"])
                if oid == tid:
                    continue
                if oid in protected_ids:
                    report["details"].append(f"skip merge source protected id={oid}")
                    continue
                detail = f"merge duplicate name '{g.get('normalized_name')}': {oid} → {tid}"
                report["details"].append(detail)
                report["merged_species_rows"] += 1
                if not dry_run:
                    merge_species_into(oid, tid)

    # 2) Подозрительные — при включённом allowlist это подмножество off_allowlist.
    # Шаг обрабатывается в шаге 3 (off_allowlist). Здесь только перекидываем флаги.
    if reassign_suspects_to_unknown and not reassign_off_allowlist_to_unknown:
        reassign_off_allowlist_to_unknown = True
    if delete_empty_suspects and not delete_empty_off_allowlist:
        delete_empty_off_allowlist = True

    # 3) Вне allowlist
    if reassign_off_allowlist_to_unknown or delete_empty_off_allowlist:
        if not allow_keys:
            report["errors"].append(
                "allowlist пуст или файл не найден (species.catalog_allowlist_file) — шаг off_allowlist пропущен.",
            )
        else:
            rows = Species.query.order_by(Species.id.asc()).all()
            uid = unknown.id if unknown else 0
            for sp in rows:
                if sp.id in protected_ids:
                    continue
                if _has_child_species(sp.id):
                    continue
                if species_matches_allowlist(sp.name or "", allow_keys, mapping):
                    continue
                active = _species_has_activity(sp.id)
                if active and reassign_off_allowlist_to_unknown and unknown:
                    report["off_allowlist_reassigned"] += 1
                    report["details"].append(f"off-allowlist → Unknown: {sp.id} {sp.name!r}")
                    if not dry_run:
                        merge_species_into(sp.id, uid)
                elif not active and delete_empty_off_allowlist:
                    report["off_allowlist_deleted_empty"] += 1
                    report["details"].append(f"delete empty off-allowlist: {sp.id} {sp.name!r}")
                    if not dry_run:
                        db.session.delete(sp)

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    report["allowlist_loaded"] = bool(allow_keys)
    report["allowlist_class_count"] = len(allow_keys) if allow_keys else 0
    return report


__all__ = ["reconcile_species_catalog"]
