"""Species summary data for /api/ui/species/:id/summary."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

from models import Video, SpeciesVisit, VideoSpecies, BirdFood, video_bird_food_association
from util import format_visit_for_timeline


def build_species_summary(session, species, children, all_species_ids: list) -> dict:
    """Build species summary response: stats, hourlyActivity, weather, food, subspecies, recentVisits."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(days=1)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    def get_visit_stats(since):
        rows = session.query(
            SpeciesVisit.species_id,
            func.sum(SpeciesVisit.max_simultaneous).label('count'),
        ).filter(
            SpeciesVisit.species_id.in_(all_species_ids),
            SpeciesVisit.start_time >= since,
        ).group_by(SpeciesVisit.species_id).all()
        return {sid: int(c or 0) for sid, c in rows}

    stats_24h = get_visit_stats(last_24h)
    stats_7d = get_visit_stats(last_7d)
    stats_30d = get_visit_stats(last_30d)

    sightings = session.query(
        func.min(SpeciesVisit.start_time).label('first'),
        func.max(SpeciesVisit.end_time).label('last'),
    ).filter(SpeciesVisit.species_id.in_(all_species_ids)).first()

    hourly_rows = session.query(
        SpeciesVisit.species_id,
        func.strftime('%H', SpeciesVisit.start_time).label('hour'),
        func.sum(SpeciesVisit.max_simultaneous).label('count'),
    ).filter(
        SpeciesVisit.species_id.in_(all_species_ids),
        SpeciesVisit.start_time >= last_30d,
    ).group_by(SpeciesVisit.species_id, 'hour').all()

    activity_by_species = {sid: [0] * 24 for sid in all_species_ids}
    activity_total = [0] * 24
    for sid, hour, count in hourly_rows:
        h = int(hour)
        activity_by_species[sid][h] = int(count or 0)
        activity_total[h] += int(count or 0)

    weather_stats = session.query(
        func.round(Video.weather_temp).label('temp'),
        Video.weather_clouds,
        func.sum(SpeciesVisit.max_simultaneous).label('count'),
    ).join(VideoSpecies, Video.id == VideoSpecies.video_id).join(
        SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id
    ).filter(
        SpeciesVisit.species_id.in_(all_species_ids),
        Video.weather_temp.isnot(None),
    ).group_by(func.round(Video.weather_temp), Video.weather_clouds).all()

    # Count distinct visits per food instead of summing max_simultaneous across
    # joined rows. This avoids inflated values when a visit has multiple linked
    # detections/videos for the same species.
    food_stats = session.query(
        BirdFood.name,
        func.count(func.distinct(SpeciesVisit.id)).label('count'),
    ).join(
        video_bird_food_association, BirdFood.id == video_bird_food_association.c.birdfood_id
    ).join(
        Video, Video.id == video_bird_food_association.c.video_id
    ).join(
        VideoSpecies, VideoSpecies.video_id == Video.id
    ).join(
        SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id
    ).filter(
        SpeciesVisit.species_id.in_(all_species_ids)
    ).group_by(
        BirdFood.name
    ).order_by(
        func.count(func.distinct(SpeciesVisit.id)).desc()
    ).limit(5).all()

    recent_visits = session.query(SpeciesVisit).filter(
        SpeciesVisit.species_id.in_(all_species_ids)
    ).order_by(SpeciesVisit.start_time.desc()).limit(10).all()

    return {
        'species': {
            'id': species.id,
            'name': species.name,
            'image_url': species.image_url,
            'description': species.description,
            'metadata_source': species.metadata_source,
            'metadata_source_url': species.metadata_source_url,
            'active': species.active,
            'parent': {'id': species.parent.id, 'name': species.parent.name} if species.parent else None,
        },
        'stats': {
            'detections': {
                'detections_24h': sum(stats_24h.values()),
                'detections_7d': sum(stats_7d.values()),
                'detections_30d': sum(stats_30d.values()),
            },
            'timeRange': {
                'first_sighting': sightings.first.isoformat() if sightings and sightings.first else None,
                'last_sighting': sightings.last.isoformat() if sightings and sightings.last else None,
            },
            'hourlyActivity': activity_total,
            'weather': [{'temp': t, 'clouds': c, 'count': int(cnt or 0)} for t, c, cnt in weather_stats],
            'food': [{'name': n, 'count': int(c or 0)} for n, c in food_stats],
        },
        'subspecies': [{
            'species': {
                'id': c.id,
                'name': c.name,
                'image_url': c.image_url,
                'metadata_source': c.metadata_source,
                'metadata_source_url': c.metadata_source_url,
            },
            'stats': {
                'detections': {
                    'detections_24h': stats_24h.get(c.id, 0),
                    'detections_7d': stats_7d.get(c.id, 0),
                    'detections_30d': stats_30d.get(c.id, 0),
                },
                'hourlyActivity': activity_by_species[c.id],
            },
        } for c in children],
        'recentVisits': [format_visit_for_timeline(v) for v in recent_visits],
    }
