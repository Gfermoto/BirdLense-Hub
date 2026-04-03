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


def _video_overlaps_window(start_of_day: datetime, end_of_day: datetime):
    return (
        Video.end_time >= start_of_day,
        Video.start_time <= end_of_day,
    )


def get_overview_data(
    session,
    start_of_day: datetime,
    end_of_day: datetime,
) -> dict:
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
        # Один визит = одно событие в часе старта (как в таймлайне), без суммы max_simultaneous.
        busiest_by_hour[hour] += 1

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
        detections[hour] += 1
        species_bucket['total'] += 1

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

    # Статистика по визитам (строки SpeciesVisit за окно), не по max_simultaneous и не по сегментам VideoSpecies.
    last_hour_start = now_utc - timedelta(hours=1)
    stats_q = session.query(
        func.count(distinct(SpeciesVisit.species_id)).label('uniqueSpecies'),
        func.count(SpeciesVisit.id).label('totalDetections'),
        func.sum(
            case(
                (
                    (SpeciesVisit.end_time >= last_hour_start)
                    & (SpeciesVisit.start_time <= now_utc),
                    1,
                ),
                else_=0,
            )
        ).label('lastHourDetections'),
    ).join(Species, SpeciesVisit.species_id == Species.id).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
        exclude_bird,
    ).first()

    # Recording time: сумма длительностей видеофайлов за день (Video.start_time в диапазоне).
    # Это «время записей» — сколько всего записали камерой.
    overlapping_videos = session.query(
        Video.start_time,
        Video.end_time,
        Video.weather_temp,
    ).filter(
        *_video_overlaps_window(start_of_day, end_of_day),
    ).all()
    video_durations = [
        max(
            0,
            round(
                (
                    ensure_utc(video_end) - ensure_utc(video_start)
                ).total_seconds(),
            ),
        )
        for video_start, video_end, _temp in overlapping_videos
        if video_start and video_end
    ]
    recording_sec = sum(video_durations)
    avg_recording_sec = (
        sum(video_durations) / len(video_durations)
        if video_durations else 0
    )

    # Detection time: сумма длительностей детекций (VideoSpecies) — сколько птиц было видно.
    # case — защита от end<start.
    dur_expr = case(
        (
            VideoSpecies.end_time >= VideoSpecies.start_time,
            VideoSpecies.end_time - VideoSpecies.start_time,
        ),
        else_=0,
    )
    dur_q = session.query(
        func.sum(
            case((VideoSpecies.source == 'video', dur_expr), else_=0)
        ).label('video_duration'),
        func.sum(
            case((VideoSpecies.source == 'audio', dur_expr), else_=0)
        ).label('audio_duration'),
    ).join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
    ).first()

    # По провайдеру: число визитов, у которых есть хотя бы один сегмент с этим detection_provider
    # (не число строк VideoSpecies — иначе не сходится с «визитами»).
    prov_q = session.query(
        VideoSpecies.detection_provider,
        func.count(distinct(SpeciesVisit.id)).label('count'),
    ).join(
        SpeciesVisit,
        VideoSpecies.species_visit_id == SpeciesVisit.id,
    ).join(
        Species,
        SpeciesVisit.species_id == Species.id,
    ).filter(
        *_visit_overlaps_window(start_of_day, end_of_day),
        exclude_bird,
    ).group_by(VideoSpecies.detection_provider).all()

    stats = {
        'uniqueSpecies': stats_q.uniqueSpecies or 0,
        'totalDetections': stats_q.totalDetections or 0,
        'lastHourDetections': stats_q.lastHourDetections or 0,
        'busiestHour': busiest if any(busiest_by_hour) else 0,
        # UI card "Mean duration": average single recording duration (Video).
        'avgVisitDuration': round(avg_recording_sec),
        'videoDuration': round(recording_sec),
        'audioDuration': round(dur_q.audio_duration or 0),
        'detectionByProvider': {(p or 'legacy'): int(c) for p, c in prov_q},
    }

    # Hourly temperature
    hourly_temperature = [None] * 24
    hourly_temp_values: dict[int, list[float]] = {}
    for video_start, _video_end, temp in overlapping_videos:
        if temp is None or video_start is None:
            continue
        bucket_time = max(video_start, start_of_day)
        hour = observer_local_hour(bucket_time)
        hourly_temp_values.setdefault(hour, []).append(float(temp))
    for hour, values in hourly_temp_values.items():
        if values:
            hourly_temperature[hour] = round(sum(values) / len(values), 1)

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
