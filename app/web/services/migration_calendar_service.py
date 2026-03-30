"""Migration calendar: species activity by month (historical data)."""
from datetime import datetime, timezone
from sqlalchemy import func, and_, select

from models import Species, SpeciesVisit, VideoSpecies
from util import GENERIC_BIRD_SPECIES
from services.species_data_quality_service import species_ids_to_exclude_from_bird_catalog


def get_migration_calendar(
    session,
    start_year: int | None = None,
    end_year: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    catalog: str = 'active',
    evidence: str = 'all',
) -> dict:
    """
    Aggregate SpeciesVisit by species and month (1-12).
    Returns species list with monthly visit counts for heatmap/calendar.
    start_year, end_year: filter by year (inclusive). None = no filter.
    start_date, end_date: filter by date (inclusive, YYYY-MM-DD, UTC).
    catalog: ``active`` — только виды с ненулевой активностью; ``full`` — весь каталог видов (нули в клетках).
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
        q = session.query(Species.id, Species.name, Species.image_url).filter(
            exclude_bird,
        )
        if suspect_ids:
            q = q.filter(~Species.id.in_(suspect_ids))
        all_species = q.all()
        for sid, name, image_url in all_species:
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
            if k not in suspect_ids
        }

    species_list = [{**v, 'total': sum(v['monthly_counts'])} for v in species_data.values()]
    if catalog == 'active':
        species_list = [s for s in species_list if s['total'] > 0]
    species_list.sort(key=lambda s: (-s['total'], (s['name'] or '').lower()))

    return {
        'species': species_list,
        'month_labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    }
