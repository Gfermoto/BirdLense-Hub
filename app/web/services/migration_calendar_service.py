"""Migration calendar: species activity by month (historical data)."""
from datetime import datetime, timezone
from sqlalchemy import func, and_, select

from models import Species, SpeciesVisit, VideoSpecies
from util import GENERIC_BIRD_SPECIES
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog
from services.species_catalog_allowlist_service import (
    load_catalog_allowlist_names,
    load_catalog_allowlist_norm_keys,
    species_matches_allowlist,
)


def get_migration_calendar(
    session,
    start_year: int | None = None,
    end_year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    catalog: str = 'active',
    evidence: str = 'all',
    app_config_get=None,
) -> dict:
    """
    Aggregate SpeciesVisit by species and month (1-12).
    Returns species list with monthly visit counts for heatmap/calendar.
    start_year, end_year: filter by year (inclusive). None = no filter.
    start_date, end_date: filter by date (inclusive, YYYY-MM-DD, UTC).
    catalog: ``active`` — только виды с ненулевой активностью;
             ``full`` — все виды из allowlist (если задан) или весь каталог БД.
    evidence: ``all`` — все визиты; ``camera``/``video`` — только визиты с видео-детекцией;
        ``birdnet`` — только визиты, где есть audio/BirdNET-детекция.
    """
    if catalog not in ('active', 'full'):
        catalog = 'active'
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

    if catalog == 'full':
        allowlist_names = load_catalog_allowlist_names(app_config_get) if app_config_get else None
        allowlist_keys = load_catalog_allowlist_norm_keys(app_config_get) if app_config_get else None

        if allowlist_names is not None:
            # Full catalog = exactly the allowlist. First, map DB species by norm key.
            q = session.query(Species.id, Species.name, Species.image_url).filter(exclude_bird)
            if suspect_ids:
                q = q.filter(~Species.id.in_(suspect_ids))
            db_species_by_key: dict[str, tuple] = {}
            for sid, sname, simg in q.all():
                import re as _re
                nk = sname.strip().lower().replace('_', ' ').replace('-', ' ')
                nk = _re.sub(r'\s+', ' ', nk)
                db_species_by_key[nk] = (sid, sname, simg)
                # Also try common name from "Scientific (Common)" format
                m = _re.match(r'^.+\(([^)]+)\)\s*$', sname.strip())
                if m:
                    cn = m.group(1).strip().lower().replace('-', ' ')
                    cn = _re.sub(r'\s+', ' ', cn)
                    db_species_by_key.setdefault(cn, (sid, sname, simg))

            used_keys: set = set()
            for aname in allowlist_names:
                import re as _re
                nk = aname.strip().lower().replace('_', ' ').replace('-', ' ')
                nk = _re.sub(r'\s+', ' ', nk)
                if nk in db_species_by_key and nk not in used_keys:
                    sid, sname, simg = db_species_by_key[nk]
                    used_keys.add(nk)
                    if sid not in species_data:
                        species_data[sid] = {
                            'id': sid,
                            'name': sname,
                            'image_url': simg,
                            'monthly_counts': [0] * 12,
                        }
                elif nk not in used_keys:
                    # Allowlist species not yet in DB — show as placeholder with zero counts
                    used_keys.add(nk)
                    placeholder_key = f'__allowlist__{nk}'
                    if placeholder_key not in species_data:
                        species_data[placeholder_key] = {
                            'id': None,
                            'name': aname,
                            'image_url': None,
                            'monthly_counts': [0] * 12,
                        }
        else:
            # No allowlist: fall back to all DB species (legacy behaviour)
            q = session.query(Species.id, Species.name, Species.image_url).filter(exclude_bird)
            if suspect_ids:
                q = q.filter(~Species.id.in_(suspect_ids))
            for sid, name, image_url in q.all():
                if sid not in species_data:
                    species_data[sid] = {
                        'id': sid,
                        'name': name,
                        'image_url': image_url,
                        'monthly_counts': [0] * 12,
                    }

    if suspect_ids:
        species_data = {
            k: v for k, v in species_data.items()
            if not isinstance(k, int) or k not in suspect_ids
        }

    species_list = [{**v, 'total': sum(v['monthly_counts'])} for v in species_data.values()]
    if catalog == 'active':
        species_list = [s for s in species_list if s['total'] > 0]
    species_list.sort(key=lambda s: (-s['total'], (s['name'] or '').lower()))

    return {
        'species': species_list,
        'month_labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    }
