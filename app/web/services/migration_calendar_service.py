"""Migration calendar: species activity by month (historical data)."""
from sqlalchemy import func, and_

from models import Species, SpeciesVisit
from util import GENERIC_BIRD_SPECIES


def get_migration_calendar(session, start_year: int | None = None, end_year: int | None = None) -> dict:
    """
    Aggregate SpeciesVisit by species and month (1-12).
    Returns species list with monthly visit counts for heatmap/calendar.
    start_year, end_year: filter by year (inclusive). None = no filter.
    """
    exclude_bird = Species.name != GENERIC_BIRD_SPECIES
    filters = [exclude_bird]
    if start_year is not None:
        filters.append(func.strftime('%Y', SpeciesVisit.start_time) >= str(start_year))
    if end_year is not None:
        filters.append(func.strftime('%Y', SpeciesVisit.start_time) <= str(end_year))

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

    # Sort by total visits descending, only species with at least one visit
    species_list = [
        {**v, 'total': sum(v['monthly_counts'])}
        for v in species_data.values()
        if sum(v['monthly_counts']) > 0
    ]
    species_list.sort(key=lambda s: s['total'], reverse=True)

    return {
        'species': species_list,
        'month_labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    }
