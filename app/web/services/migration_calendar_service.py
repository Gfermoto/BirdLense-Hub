"""Migration calendar: species activity by month (historical data)."""

from datetime import datetime, timezone
import os

from sqlalchemy import and_, func

from models import Species, SpeciesVisit
from services.species_catalog_allowlist_service import (
    load_catalog_allowlist_names,
    species_name_match_norm_keys,
)
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog
from species_constants import GENERIC_BIRD_SPECIES
from util import data_dir


def _norm_key(name: str) -> str:
    return " ".join((name or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _dataset_class_names(app_config_get=None) -> set[str]:
    web_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.abspath(os.path.join(web_root, "..", ".."))
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
                        out.add(_folder_display_name(entry))
            except OSError:
                continue
    allow_names = load_catalog_allowlist_names(app_config_get) if app_config_get else None
    if allow_names:
        out.update(str(x).strip() for x in allow_names if str(x).strip())
    return out


def _folder_display_name(folder: str) -> str:
    return " ".join((folder or "").replace("_", " ").split()).strip()


def get_migration_calendar(
    session,
    start_year: int | None = None,
    end_year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    catalog: str = "observed",
    evidence: str = "all",
    metric: str = "encounters",
    app_config_get=None,
) -> dict:
    """
    Aggregate SpeciesVisit by species and month (1-12).
    Returns species list with monthly visit counts for heatmap/calendar.
    start_year, end_year: filter by year (inclusive). None = no filter.
    start_date, end_date: filter by date (inclusive, YYYY-MM-DD, UTC).
    catalog: ``observed`` — только виды с ненулевой активностью;
             ``dataset`` — виды, присутствующие в data/dataset/*;
             ``full_eu`` — полный каталог из allowlist EU.
             Legacy aliases: ``active`` -> ``observed``, ``full`` -> ``full_eu``.
    evidence: legacy field, ignored for catalog output.
    """
    catalog = (catalog or "observed").strip().lower()
    requested_metric = (metric or "encounters").strip().lower()
    if requested_metric not in {"encounters", "visits", "max_simultaneous"}:
        requested_metric = "encounters"
    selected_metric = "visits" if requested_metric in {"encounters", "visits"} else "max_simultaneous"
    if catalog == "active":
        catalog = "observed"
    elif catalog in ("full", "all"):
        catalog = "full_eu"
    if catalog not in ("observed", "dataset", "full_eu"):
        catalog = "observed"
    # Evidence split (camera vs BirdNET) is intentionally disabled in catalog.

    suspect_ids = species_ids_to_exclude_from_bird_catalog(session)

    exclude_bird = Species.name != GENERIC_BIRD_SPECIES
    filters = [exclude_bird]
    if start_year is not None:
        filters.append(func.strftime("%Y", SpeciesVisit.start_time) >= str(start_year))
    if end_year is not None:
        filters.append(func.strftime("%Y", SpeciesVisit.start_time) <= str(end_year))
    if start_date:
        start_dt = datetime.fromisoformat(start_date).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=timezone.utc,
        )
        filters.append(SpeciesVisit.start_time >= start_dt)
    if end_date:
        end_dt = datetime.fromisoformat(end_date).replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
            tzinfo=timezone.utc,
        )
        filters.append(SpeciesVisit.start_time <= end_dt)

    # Per species: count visits per month (all years in range combined)
    month_expr = func.strftime("%m", SpeciesVisit.start_time)
    rows = (
        session.query(
            Species.id,
            Species.name,
            Species.image_url,
            month_expr.label("month"),
            func.count(SpeciesVisit.id).label("visit_count"),
            func.sum(SpeciesVisit.max_simultaneous).label("max_simultaneous_count"),
        )
        .join(SpeciesVisit, SpeciesVisit.species_id == Species.id)
        .filter(
            and_(*filters),
        )
        .group_by(Species.id, Species.name, Species.image_url, month_expr)
        .all()
    )

    # Build species -> [12 monthly counts] (month is '01'..'12')
    species_data = {}
    for sid, name, image_url, month_str, visit_count, max_simultaneous_count in rows:
        if sid not in species_data:
            species_data[sid] = {
                "id": sid,
                "name": name,
                "image_url": image_url,
                "monthly_counts": [0] * 12,
                "monthly_visit_counts": [0] * 12,
                "monthly_max_simultaneous_counts": [0] * 12,
            }
        try:
            m = int(month_str)
            if 1 <= m <= 12:
                species_data[sid]["monthly_visit_counts"][m - 1] = int(visit_count or 0)
                species_data[sid]["monthly_max_simultaneous_counts"][m - 1] = int(max_simultaneous_count or 0)
        except (ValueError, TypeError):
            pass

    q = session.query(Species.id, Species.name, Species.image_url).filter(exclude_bird)
    if suspect_ids:
        q = q.filter(~Species.id.in_(suspect_ids))
    all_db_species = q.all()

    db_by_norm: dict[str, tuple[int, str, str | None]] = {}
    for sid, sname, simg in all_db_species:
        for mk in species_name_match_norm_keys(sname or ""):
            db_by_norm.setdefault(mk, (sid, sname, simg))

    if catalog == "full_eu":
        allowlist_names = load_catalog_allowlist_names(app_config_get) if app_config_get else None
        if allowlist_names:
            for aname in allowlist_names:
                match = None
                for mk in species_name_match_norm_keys(aname):
                    if mk in db_by_norm:
                        match = db_by_norm[mk]
                        break
                if match:
                    sid, sname, simg = match
                    if sid not in species_data:
                        species_data[sid] = {
                            "id": sid,
                            "name": sname,
                            "image_url": simg,
                            "monthly_counts": [0] * 12,
                            "monthly_visit_counts": [0] * 12,
                            "monthly_max_simultaneous_counts": [0] * 12,
                        }
                else:
                    # Keep in full EU view even if DB row is missing.
                    key = f"__allowlist__{_norm_key(aname)}"
                    species_data.setdefault(
                        key,
                        {
                            "id": None,
                            "name": aname,
                            "image_url": None,
                            "monthly_counts": [0] * 12,
                            "monthly_visit_counts": [0] * 12,
                            "monthly_max_simultaneous_counts": [0] * 12,
                        },
                    )
        else:
            # Legacy fallback when allowlist is not configured.
            for sid, sname, simg in all_db_species:
                species_data.setdefault(
                    sid,
                    {
                        "id": sid,
                        "name": sname,
                        "image_url": simg,
                        "monthly_counts": [0] * 12,
                        "monthly_visit_counts": [0] * 12,
                        "monthly_max_simultaneous_counts": [0] * 12,
                    },
                )

    elif catalog == "dataset":
        for folder in sorted(_dataset_class_names(app_config_get)):
            match = None
            for mk in species_name_match_norm_keys(_folder_display_name(folder)):
                if mk in db_by_norm:
                    match = db_by_norm[mk]
                    break
            if match:
                sid, sname, simg = match
                if sid not in species_data:
                    species_data[sid] = {
                        "id": sid,
                        "name": sname,
                        "image_url": simg,
                        "monthly_counts": [0] * 12,
                        "monthly_visit_counts": [0] * 12,
                        "monthly_max_simultaneous_counts": [0] * 12,
                    }
            else:
                # Keep unmatched folders visible: local dataset may include classes
                # not yet materialized in Species table.
                key = f"__dataset__{_norm_key(folder)}"
                species_data.setdefault(
                    key,
                    {
                        "id": None,
                        "name": _folder_display_name(folder),
                        "image_url": None,
                        "monthly_counts": [0] * 12,
                        "monthly_visit_counts": [0] * 12,
                        "monthly_max_simultaneous_counts": [0] * 12,
                    },
                )

    if suspect_ids:
        species_data = {k: v for k, v in species_data.items() if not isinstance(k, int) or k not in suspect_ids}

    for payload in species_data.values():
        payload["monthly_counts"] = (
            payload["monthly_max_simultaneous_counts"]
            if selected_metric == "max_simultaneous"
            else payload["monthly_visit_counts"]
        )
    species_list = [{**v, "total": sum(v["monthly_counts"])} for v in species_data.values()]
    if catalog == "observed":
        species_list = [s for s in species_list if s["total"] > 0]
    species_list.sort(key=lambda s: (-s["total"], (s["name"] or "").lower()))

    return {
        "catalog": catalog,
        "metric_used": requested_metric,
        "species": species_list,
        "month_labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    }
