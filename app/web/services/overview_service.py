"""Overview data aggregation for /api/ui/overview."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case, distinct

from models import Video, Species, SpeciesVisit, VideoSpecies
from util import ensure_utc, GENERIC_BIRD_SPECIES
from services.cache import cache_get, cache_set


def get_overview_data(session, start_of_day: datetime, end_of_day: datetime) -> dict:
    """Build overview payload: topSpecies, stats, hourlyTemperature, lastDetection."""
    cache_key = f"overview:{start_of_day.isoformat()}:{end_of_day.isoformat()}"
    found, cached_result = cache_get(cache_key)
    if found:
        return cached_result

    exclude_bird = Species.name != GENERIC_BIRD_SPECIES
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # Top species
    top_species_query = session.query(
        Species.id.label('id'),
        Species.name.label('name'),
        *[
            func.sum(
                case(
                    (func.strftime('%H', SpeciesVisit.start_time) == str(h).zfill(2),
                     SpeciesVisit.max_simultaneous),
                    else_=0
                )
            ).label(f'detection_hour_{h}')
            for h in range(24)
        ]
    ).join(SpeciesVisit, SpeciesVisit.species_id == Species.id).filter(
        SpeciesVisit.start_time >= start_of_day,
        SpeciesVisit.start_time <= end_of_day,
        exclude_bird,
    ).group_by(Species.id, Species.name).order_by(
        func.sum(SpeciesVisit.max_simultaneous).desc()
    ).limit(10)

    top_species = [
        {
            'id': s.id,
            'name': s.name,
            'detections': [getattr(s, f'detection_hour_{h}', 0) or 0 for h in range(24)],
        }
        for s in top_species_query
    ]

    # Busiest hour
    busiest = session.query(
        func.strftime('%H', SpeciesVisit.start_time).label('hour'),
        func.sum(SpeciesVisit.max_simultaneous).label('visit_count'),
    ).join(Species, SpeciesVisit.species_id == Species.id).filter(
        SpeciesVisit.start_time >= start_of_day,
        SpeciesVisit.start_time <= end_of_day,
        exclude_bird,
    ).group_by('hour').order_by(
        func.sum(SpeciesVisit.max_simultaneous).desc()
    ).first()

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
        SpeciesVisit.start_time >= start_of_day,
        SpeciesVisit.start_time <= end_of_day,
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
        SpeciesVisit.start_time >= start_of_day,
        SpeciesVisit.start_time <= end_of_day,
    ).first()

    # Provider counts
    prov_q = session.query(
        VideoSpecies.detection_provider,
        func.sum(SpeciesVisit.max_simultaneous).label('count'),
    ).join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id).join(
        Species, SpeciesVisit.species_id == Species.id
    ).filter(
        SpeciesVisit.start_time >= start_of_day,
        SpeciesVisit.start_time <= end_of_day,
        exclude_bird,
    ).group_by(VideoSpecies.detection_provider).all()

    stats = {
        'uniqueSpecies': stats_q.uniqueSpecies or 0,
        'totalDetections': stats_q.totalDetections or 0,
        'lastHourDetections': stats_q.lastHourDetections or 0,
        'busiestHour': int(busiest.hour) if busiest else 0,
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
        SpeciesVisit.start_time >= start_of_day,
        SpeciesVisit.start_time <= end_of_day,
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
    }
    cache_set(cache_key, result, ttl_seconds=60)
    return result
