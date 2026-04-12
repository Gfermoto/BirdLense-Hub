"""GET/POST tuning targets для дообучения (#293)."""

from __future__ import annotations

import os

from sqlalchemy import func

from app_config.app_config import app_config
from models import Species, SpeciesVisit
from services.dataset_export_service import _sanitize_dirname


def get_tuning_target_ids() -> list[int]:
    raw = app_config.get("species.tuning_target_species_ids") or []
    out: list[int] = []
    if isinstance(raw, list):
        for x in raw:
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v > 0:
                out.append(v)
    return sorted(set(out))


def save_tuning_target_ids(ids: list[int]) -> None:
    species_cfg = app_config.config.get("species") or {}
    species_cfg["tuning_target_species_ids"] = sorted(
        set(int(x) for x in ids if int(x) > 0),
    )
    app_config.config["species"] = species_cfg
    app_config.save()


def dataset_class_folders() -> set[str]:
    web_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.abspath(os.path.join(web_root, "..", ".."))
    from util import data_dir

    candidates = [
        os.path.join(data_dir(), "dataset"),
        os.path.join(repo_root, "datasets", "merged_cls"),
    ]
    out: set[str] = set()
    for base in candidates:
        for split in ("train", "val"):
            root = os.path.join(base, split)
            if not os.path.isdir(root):
                continue
            try:
                for entry in os.listdir(root):
                    if os.path.isdir(os.path.join(root, entry)):
                        out.add(entry)
            except OSError:
                continue
    return out


def build_tuning_targets_payload(session) -> dict:
    ids = get_tuning_target_ids()
    if not ids:
        return {"ids": [], "targets": []}
    species_rows = session.query(Species).filter(Species.id.in_(ids)).all()
    by_id = {s.id: s for s in species_rows}

    observed_rows = (
        session.query(
            SpeciesVisit.species_id,
            func.coalesce(func.sum(SpeciesVisit.max_simultaneous), 0),
        )
        .filter(SpeciesVisit.species_id.in_(ids))
        .group_by(SpeciesVisit.species_id)
        .all()
    )
    observed = {int(sid): int(cnt or 0) for sid, cnt in observed_rows if sid is not None}

    folders = dataset_class_folders()
    targets = []
    for sid in ids:
        sp = by_id.get(sid)
        if not sp:
            continue
        in_dataset = _sanitize_dirname(sp.name or "") in folders
        targets.append(
            {
                "id": sid,
                "name": sp.name,
                "observed_count": observed.get(sid, 0),
                "in_dataset": bool(in_dataset),
                "in_full_catalog": True,
            }
        )
    return {"ids": ids, "targets": targets}


def apply_tuning_target_toggle(session, species_id: int, enabled: bool) -> dict:
    sp = session.get(Species, species_id)
    if not sp:
        return {"error": "Species not found"}
    ids = get_tuning_target_ids()
    id_set = set(ids)
    if enabled:
        id_set.add(species_id)
    else:
        id_set.discard(species_id)
    save_tuning_target_ids(sorted(id_set))
    return {
        "ok": True,
        "species_id": species_id,
        "enabled": enabled,
        "tuning_target_species_ids": sorted(id_set),
    }
