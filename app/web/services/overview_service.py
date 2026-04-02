"""Overview data aggregation for /api/ui/overview."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case, distinct

from models import Video, Species, SpeciesVisit, VideoSpecies
from util import (
    ensure_utc,
    GENERIC_BIRD_SPECIES,
    observer_local_hour,
    get_observer_timezone_name,
)
from services.cache import cache_get, cache_set


def _visit_overlaps_window(start_of_day: datetime, end_of_day: datetime):
    return (
        SpeciesVisit.end_time >= start_of_day,
        SpeciesVisit.start_time <= end_of_day,
    )


def get_overview_data(session, start_of_day: datetime, end_of_day: datetime) -> dict:
    """Build overview payload: topSpecies, stats, hourlyTemperature, lastDetection."""
    cache_key = f"overview:{start_of_day.isoformat()}:{end_of_day.isoformat()}"
    found, cached_result = cache_get(cache_key)
    if found:
        return cached_result

    exclude_bird = Species.name != GENERIC_BIRD_SPECIES
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    overview_visits = session.query(SpeciesVisit).join(Species).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
        exclude_bird,
    ).all()

    species_hourly: dict[int, dict[str, object]] = {}
    busiest_by_hour = [0] * 24
    for visit in overview_visits:
        bucket_time = max(visit.start_time, start_of_day)
        hour = observer_local_hour(bucket_time)
        busiest_by_hour[hour] += int(visit.max_simultaneous or 0)

        species_bucket = species_hourly.setdefault(
            visit.species_id,
            {
                'id': visit.species.id,
                'name': visit.species.name,
                'detections': [0] * 24,
                'total': 0,
            },
        )
        detections = species_bucket['detections']
        detections[hour] += int(visit.max_simultaneous or 0)
        species_bucket['total'] += int(visit.max_simultaneous or 0)

    top_species = [
        {
            'id': row['id'],
            'name': row['name'],
            'detections': row['detections'],
        }
        for row in sorted(
            species_hourly.values(),
            key=lambda row: row['total'],
            reverse=True,
        )[:10]
    ]
    busiest = max(range(24), key=lambda hour: busiest_by_hour[hour], default=0)

    # Stats based on visits
    stats_q = session.query(
        func.count(distinct(SpeciesVisit.species_id)).label('uniqueSpecies'),
        func.sum(SpeciesVisit.max_simultaneous).label('totalDetections'),
        func.sum(
            case(
                (SpeciesVisit.start_time >= now_utc - timedelta(hours=1),
                 SpeciesVisit.max_simultaneous),
                else_=0
            )
        ).label('lastHourDetections'),
    ).join(Species, SpeciesVisit.species_id == Species.id).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
        exclude_bird,
    ).first()

    # Recording time: сумма длительностей видеофайлов за день (Video.start_time в диапазоне).
    # Это «время записей» — сколько всего записали камерой.
    video_dur_expr = (
        func.strftime('%s', Video.end_time) - func.strftime('%s', Video.start_time)
    )
    recording_sec = session.query(
        func.sum(video_dur_expr).label('total'),
    ).filter(
        Video.start_time >= start_of_day,
        Video.start_time <= end_of_day,
    ).scalar() or 0
    avg_recording_sec = session.query(
        func.avg(video_dur_expr).label('avg'),
    ).filter(
        Video.start_time >= start_of_day,
        Video.start_time <= end_of_day,
    ).scalar() or 0

    # Detection time: сумма длительностей детекций (VideoSpecies) — сколько птиц было видно.
    # case — защита от end<start.
    dur_expr = case(
        (VideoSpecies.end_time >= VideoSpecies.start_time,
         VideoSpecies.end_time - VideoSpecies.start_time),
        else_=0
    )
    dur_q = session.query(
        func.sum(case((VideoSpecies.source == 'video', dur_expr), else_=0)).label('video_duration'),
        func.sum(case((VideoSpecies.source == 'audio', dur_expr), else_=0)).label('audio_duration'),
    ).join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
    ).first()

    # Provider counts
    prov_q = session.query(
        VideoSpecies.detection_provider,
        func.count(VideoSpecies.id).label('count'),
    ).join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id).join(
        Species, SpeciesVisit.species_id == Species.id
    ).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
        exclude_bird,
    ).group_by(VideoSpecies.detection_provider).all()

    stats = {
        'uniqueSpecies': stats_q.uniqueSpecies or 0,
        'totalDetections': stats_q.totalDetections or 0,
        'lastHourDetections': stats_q.lastHourDetections or 0,
        'busiestHour': busiest if any(busiest_by_hour) else 0,
        # UI card "Mean duration": average single recording duration (Video), not visit span.
        'avgVisitDuration': round(avg_recording_sec),
        'videoDuration': round(recording_sec),  # время записей: сумма длительностей видеофайлов
        'audioDuration': round(dur_q.audio_duration or 0),
        'detectionByProvider': {(p or 'legacy'): int(c) for p, c in prov_q},
    }

    # Hourly temperature
    temp_q = session.query(
        func.strftime('%H', Video.start_time).label('hour'),
        func.avg(Video.weather_temp).label('avg_temp'),
    ).filter(
        Video.start_time >= start_of_day,
        Video.start_time <= end_of_day,
        Video.weather_temp.isnot(None),
    ).group_by('hour').all()

    hourly_temperature = [None] * 24
    for h, avg in temp_q:
        hourly_temperature[int(h)] = round(avg, 1) if avg else None

    # Last detection
    last_row = session.query(SpeciesVisit, Species.name).join(
        Species, SpeciesVisit.species_id == Species.id
    ).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
    ).order_by(SpeciesVisit.end_time.desc()).first()

    last_detection = None
    if last_row:
        visit, species_name = last_row
        et = ensure_utc(visit.end_time) if visit.end_time else None
        last_detection = {
            'species_name': species_name,
            'start_time': et.isoformat() if et else None,
        }

    result = {
        'topSpecies': top_species,
        'stats': stats,
        'hourlyTemperature': hourly_temperature,
        'lastDetection': last_detection,
        'observer_timezone': get_observer_timezone_name(),
    }
    cache_set(cache_key, result, ttl_seconds=60)
    return result
