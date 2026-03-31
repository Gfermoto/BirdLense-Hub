"""Migration calendar: species activity by month (historical data)."""
from datetime import datetime, timezone
import os

from sqlalchemy import and_, func, select

from models import Species, SpeciesVisit, VideoSpecies
from services.species_catalog_allowlist_service import (
    load_catalog_allowlist_names,
    species_name_match_norm_keys,
)
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog
from util import GENERIC_BIRD_SPECIES, data_dir


def _norm_key(name: str) -> str:
    return ' '.join((name or '').strip().lower().replace('_', ' ').replace('-', ' ').split())


def _dataset_folder_names() -> set[str]:
    base = os.path.join(data_dir(), 'dataset')
    out: set[str] = set()
    for split in ('train', 'val'):
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


def get_migration_calendar(
    session,
    start_year: int | None = None,
    end_year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    catalog: str = 'observed',
    evidence: str = 'all',
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
    evidence: ``all`` — все визиты; ``camera``/``video`` — только визиты с видео-детекцией;
        ``birdnet`` — только визиты, где есть audio/BirdNET-детекция.
    """
    catalog = (catalog or 'observed').strip().lower()
    if catalog == 'active':
        catalog = 'observed'
    elif catalog == 'full':
        catalog = 'full_eu'
    if catalog not in ('observed', 'dataset', 'full_eu'):
        catalog = 'observed'
    if evidence == 'video':
        evidence = 'camera'
    if evidence not in ('all', 'camera', 'birdnet'):
        evidence = 'all'

    suspect_ids = species_ids_to_exclude_from_bird_catalog(session)

    exclude_bird = Species.name != GENERIC_BIRD_SPECIES
    filters = [exclude_bird]
    if start_year is not None:
        filters.append(func.strftime('%Y', SpeciesVisit.start_time) >= str(start_year))
    if end_year is not None:
        filters.append(func.strftime('%Y', SpeciesVisit.start_time) <= str(end_year))
    if start_date:
        start_dt = datetime.fromisoformat(start_date).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc,
        )
        filters.append(SpeciesVisit.start_time >= start_dt)
    if end_date:
        end_dt = datetime.fromisoformat(end_date).replace(
            hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc,
        )
        filters.append(SpeciesVisit.start_time <= end_dt)

    if evidence == 'camera':
        vid_visits = (
            select(SpeciesVisit.id)
            .join(VideoSpecies, VideoSpecies.species_visit_id == SpeciesVisit.id)
            .where(VideoSpecies.source == 'video')
            .distinct()
        )
        filters.append(SpeciesVisit.id.in_(vid_visits))
    elif evidence == 'birdnet':
        birdnet_visits = (
            select(SpeciesVisit.id)
            .join(VideoSpecies, VideoSpecies.species_visit_id == SpeciesVisit.id)
            .where(
                (VideoSpecies.detection_provider == 'birdnet_mqtt')
                | (VideoSpecies.source == 'audio')
            )
            .distinct()
        )
        filters.append(SpeciesVisit.id.in_(birdnet_visits))

    # Per species: count visits per month (all years in range combined)
    month_expr = func.strftime('%m', SpeciesVisit.start_time)
    rows = session.query(
        Species.id,
        Species.name,
        Species.image_url,
        month_expr.label('month'),
        func.sum(SpeciesVisit.max_simultaneous).label('count'),
    ).join(SpeciesVisit, SpeciesVisit.species_id == Species.id).filter(
        and_(*filters),
    ).group_by(Species.id, Species.name, Species.image_url, month_expr).all()

    # Build species -> [12 monthly counts] (month is '01'..'12')
    species_data = {}
    for sid, name, image_url, month_str, count in rows:
        if sid not in species_data:
            species_data[sid] = {
                'id': sid,
                'name': name,
                'image_url': image_url,
                'monthly_counts': [0] * 12,
            }
        try:
            m = int(month_str)
            if 1 <= m <= 12:
                species_data[sid]['monthly_counts'][m - 1] = int(count or 0)
        except (ValueError, TypeError):
            pass

    q = session.query(Species.id, Species.name, Species.image_url).filter(exclude_bird)
    if suspect_ids:
        q = q.filter(~Species.id.in_(suspect_ids))
    all_db_species = q.all()

    db_by_norm: dict[str, tuple[int, str, str | None]] = {}
    for sid, sname, simg in all_db_species:
        for mk in species_name_match_norm_keys(sname or ''):
            db_by_norm.setdefault(mk, (sid, sname, simg))

    if catalog == 'full_eu':
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
                            'id': sid,
                            'name': sname,
                            'image_url': simg,
                            'monthly_counts': [0] * 12,
                        }
                else:
                    # Keep in full EU view even if DB row is missing.
                    key = f"__allowlist__{_norm_key(aname)}"
                    species_data.setdefault(key, {
                        'id': None,
                        'name': aname,
                        'image_url': None,
                        'monthly_counts': [0] * 12,
                    })
        else:
            # Legacy fallback when allowlist is not configured.
            for sid, sname, simg in all_db_species:
                species_data.setdefault(sid, {
                    'id': sid,
                    'name': sname,
                    'image_url': simg,
                    'monthly_counts': [0] * 12,
                })

    elif catalog == 'dataset':
        for folder in sorted(_dataset_folder_names()):
            match = None
            for mk in species_name_match_norm_keys(folder):
                if mk in db_by_norm:
                    match = db_by_norm[mk]
                    break
            if match:
                sid, sname, simg = match
                if sid not in species_data:
                    species_data[sid] = {
                        'id': sid,
                        'name': sname,
                        'image_url': simg,
                        'monthly_counts': [0] * 12,
                    }

    if suspect_ids:
        species_data = {
            k: v for k, v in species_data.items()
            if not isinstance(k, int) or k not in suspect_ids
        }

    species_list = [{**v, 'total': sum(v['monthly_counts'])} for v in species_data.values()]
    if catalog == 'observed':
        species_list = [s for s in species_list if s['total'] > 0]
    species_list.sort(key=lambda s: (-s['total'], (s['name'] or '').lower()))

    return {
        'catalog': catalog,
        'species': species_list,
        'month_labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    }
