"""Overview data aggregation for /api/ui/overview."""

from datetime import datetime, timezone, timedelta

from sqlalchemy import func, case, distinct, exists
from sqlalchemy.orm import contains_eager

from models import Video, Species, SpeciesVisit, VideoSpecies
from species_constants import (
    GENERIC_BIRD_NAME_KEYS,
    GENERIC_BIRD_SPECIES,
    GENERIC_RODENT_NAME_KEYS,
    GENERIC_RODENT_SPECIES,
    is_generic_bird_species_name,
    is_generic_rodent_species_name,
)
from util import (
    ensure_utc,
    observer_local_hour,
    get_observer_timezone_name,
)
from services.cache import cache_get, cache_set

_UNIDENTIFIED_SPECIES_KEYS = list(GENERIC_BIRD_NAME_KEYS | GENERIC_RODENT_NAME_KEYS)
_SYNTHETIC_BIRD_SPECIES_ID = 0
_SYNTHETIC_RODENT_SPECIES_ID = -1


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


def _has_video_detection():
    """SpeciesVisit must have at least one VideoSpecies row (not orphan)."""
    return exists().where(VideoSpecies.species_visit_id == SpeciesVisit.id).correlate(SpeciesVisit)


def _exclude_named_species_stats():
    """Named-species dashboard stats exclude generic bird and rodent taxa."""
    return func.lower(Species.name).notin_(_UNIDENTIFIED_SPECIES_KEYS)


def _bucket_video_species_hour(video_start: datetime, segment_start_s: float, day_start: datetime) -> int:
    base = ensure_utc(video_start)
    if base.tzinfo is not None:
        base = base.replace(tzinfo=None)
    try:
        offset = float(segment_start_s or 0.0)
    except (TypeError, ValueError):
        offset = 0.0
    bucket_time = max(base + timedelta(seconds=offset), day_start)
    return observer_local_hour(bucket_time)


def _collect_unidentified_activity(
    session,
    *,
    start_of_day: datetime,
    end_of_day: datetime,
) -> tuple[int, int, list[int], list[int], int]:
    """YOLO/MQTT segments for generic Bird or Rodent (classifier not required)."""
    rows = (
        session.query(
            Species.name,
            Video.start_time,
            Video.end_time,
            VideoSpecies.start_time,
        )
        .join(Video, VideoSpecies.video_id == Video.id)
        .join(Species, VideoSpecies.species_id == Species.id)
        .filter(
            *_video_overlaps_window(start_of_day, end_of_day),
            func.lower(Species.name).in_(_UNIDENTIFIED_SPECIES_KEYS),
        )
        .all()
    )
    bird_hourly = [0] * 24
    rodent_hourly = [0] * 24
    bird_total = 0
    rodent_total = 0
    last_hour_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    last_hour_unidentified = 0
    for name, video_start, video_end, seg_start in rows:
        if not video_start:
            continue
        hour = _bucket_video_species_hour(video_start, seg_start, start_of_day)
        if is_generic_rodent_species_name(name):
            rodent_hourly[hour] += 1
            rodent_total += 1
        elif is_generic_bird_species_name(name):
            bird_hourly[hour] += 1
            bird_total += 1
        if video_end and video_end >= last_hour_start and video_start <= datetime.now(timezone.utc).replace(
            tzinfo=None
        ):
            last_hour_unidentified += 1
    return bird_total, rodent_total, bird_hourly, rodent_hourly, last_hour_unidentified


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

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    visit_base_filters = (
        *_visit_overlaps_window(start_of_day, end_of_day),
        _has_video_detection(),
        _exclude_named_species_stats(),
    )

    bird_activity, rodent_activity, bird_hourly, rodent_hourly, last_hour_unidentified = (
        _collect_unidentified_activity(session, start_of_day=start_of_day, end_of_day=end_of_day)
    )

    overview_visits = (
        session.query(SpeciesVisit)
        .join(SpeciesVisit.species)
        .options(contains_eager(SpeciesVisit.species))
        .filter(*visit_base_filters)
        .all()
    )

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
                "id": visit.species.id,
                "name": visit.species.name,
                "detections": [0] * 24,
                "total": 0,
                "unidentified": False,
            },
        )
        detections = species_bucket["detections"]
        detections[hour] += 1
        species_bucket["total"] += 1

    for hour in range(24):
        busiest_by_hour[hour] += bird_hourly[hour] + rodent_hourly[hour]

    top_species = [
        {
            "id": row["id"],
            "name": row["name"],
            "detections": row["detections"],
            **({"unidentified": True} if row.get("unidentified") else {}),
        }
        for row in sorted(
            species_hourly.values(),
            key=lambda row: row["total"],
            reverse=True,
        )[:10]
    ]
    if bird_activity > 0:
        top_species.append(
            {
                "id": _SYNTHETIC_BIRD_SPECIES_ID,
                "name": GENERIC_BIRD_SPECIES,
                "detections": bird_hourly,
                "unidentified": True,
            }
        )
    if rodent_activity > 0:
        top_species.append(
            {
                "id": _SYNTHETIC_RODENT_SPECIES_ID,
                "name": GENERIC_RODENT_SPECIES,
                "detections": rodent_hourly,
                "unidentified": True,
            }
        )
    busiest = max(range(24), key=lambda hour: busiest_by_hour[hour], default=0)

    # Статистика по визитам (строки SpeciesVisit за окно), не по max_simultaneous и не по сегментам VideoSpecies.
    last_hour_start = now_utc - timedelta(hours=1)
    stats_q = (
        session.query(
            func.count(distinct(SpeciesVisit.species_id)).label("uniqueSpecies"),
            func.count(SpeciesVisit.id).label("totalDetections"),
            func.sum(
                case(
                    (
                        (SpeciesVisit.end_time >= last_hour_start) & (SpeciesVisit.start_time <= now_utc),
                        1,
                    ),
                    else_=0,
                )
            ).label("lastHourDetections"),
        )
        .join(Species, SpeciesVisit.species_id == Species.id)
        .filter(*visit_base_filters)
        .first()
    )

    # Recording time: сумма длительностей видеофайлов за день (Video.start_time в диапазоне).
    # Это «время записей» — сколько всего записали камерой.
    overlapping_videos = (
        session.query(
            Video.start_time,
            Video.end_time,
            Video.weather_temp,
        )
        .filter(
            *_video_overlaps_window(start_of_day, end_of_day),
        )
        .all()
    )
    video_durations = [
        max(
            0,
            round(
                (ensure_utc(video_end) - ensure_utc(video_start)).total_seconds(),
            ),
        )
        for video_start, video_end, _temp in overlapping_videos
        if video_start and video_end
    ]
    recording_sec = sum(video_durations)
    avg_recording_sec = sum(video_durations) / len(video_durations) if video_durations else 0

    # Detection time: сумма длительностей детекций (VideoSpecies) — сколько птиц было видно.
    # case — защита от end<start.
    dur_expr = case(
        (
            VideoSpecies.end_time >= VideoSpecies.start_time,
            VideoSpecies.end_time - VideoSpecies.start_time,
        ),
        else_=0,
    )
    dur_q = (
        session.query(
            func.sum(case((VideoSpecies.source == "video", dur_expr), else_=0)).label("video_duration"),
            func.sum(case((VideoSpecies.source == "audio", dur_expr), else_=0)).label("audio_duration"),
        )
        .join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id)
        .join(Species, SpeciesVisit.species_id == Species.id)
        .filter(
            *_visit_overlaps_window(start_of_day, end_of_day),
            _exclude_named_species_stats(),
        )
        .first()
    )

    named_visits = int(stats_q.totalDetections or 0)
    named_last_hour = int(stats_q.lastHourDetections or 0)
    total_activity = named_visits + bird_activity + rodent_activity
    # Число визитов, у которых есть хотя бы один сегмент с этим detection_provider
    # (не число строк VideoSpecies — иначе не сходится с «визитами»).
    prov_q = (
        session.query(
            VideoSpecies.detection_provider,
            func.count(distinct(SpeciesVisit.id)).label("count"),
        )
        .join(
            SpeciesVisit,
            VideoSpecies.species_visit_id == SpeciesVisit.id,
        )
        .join(
            Species,
            SpeciesVisit.species_id == Species.id,
        )
        .filter(*visit_base_filters)
        .group_by(VideoSpecies.detection_provider)
        .all()
    )
    # По источнику срабатывания триггера: число визитов, где есть ролик
    # с соответствующим Video.trigger_source.
    trigger_q = (
        session.query(
            Video.trigger_source,
            func.count(distinct(SpeciesVisit.id)).label("count"),
        )
        .join(VideoSpecies, Video.id == VideoSpecies.video_id)
        .join(SpeciesVisit, VideoSpecies.species_visit_id == SpeciesVisit.id)
        .join(Species, SpeciesVisit.species_id == Species.id)
        .filter(*visit_base_filters)
        .group_by(Video.trigger_source)
        .all()
    )

    stats = {
        "uniqueSpecies": stats_q.uniqueSpecies or 0,
        "totalDetections": named_visits,
        "lastHourDetections": named_last_hour + last_hour_unidentified,
        "unidentifiedBirdDetections": bird_activity,
        "rodentDetections": rodent_activity,
        "totalActivity": total_activity,
        "busiestHour": busiest if any(busiest_by_hour) else 0,
        # UI card "Mean duration": average single recording duration (Video).
        "avgVisitDuration": round(avg_recording_sec),
        "videoDuration": round(recording_sec),
        "audioDuration": round(dur_q.audio_duration or 0),
        "detectionByProvider": {(p or "legacy"): int(c) for p, c in prov_q},
        "triggerBySource": {(src or "unknown"): int(c) for src, c in trigger_q},
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

    # Last detection — named species only (skip generic Bird / Unknown Bird).
    last_row = (
        session.query(SpeciesVisit, Species.name)
        .join(Species, SpeciesVisit.species_id == Species.id)
        .filter(*visit_base_filters)
        .order_by(SpeciesVisit.end_time.desc())
        .first()
    )

    last_detection = None
    if last_row:
        visit, species_name = last_row
        et = ensure_utc(visit.end_time) if visit.end_time else None
        last_detection = {
            "species_name": species_name,
            "start_time": et.isoformat() if et else None,
            "unidentified": False,
        }
    else:
        last_unidentified = (
            session.query(Species.name, Video.end_time)
            .join(Video, VideoSpecies.video_id == Video.id)
            .join(Species, VideoSpecies.species_id == Species.id)
            .filter(
                *_video_overlaps_window(start_of_day, end_of_day),
                func.lower(Species.name).in_(_UNIDENTIFIED_SPECIES_KEYS),
            )
            .order_by(Video.end_time.desc())
            .first()
        )
        if last_unidentified:
            species_name, end_time = last_unidentified
            et = ensure_utc(end_time) if end_time else None
            last_detection = {
                "species_name": species_name,
                "start_time": et.isoformat() if et else None,
                "unidentified": True,
            }

    result = {
        "topSpecies": top_species,
        "stats": stats,
        "hourlyTemperature": hourly_temperature,
        "lastDetection": last_detection,
        "observer_timezone": get_observer_timezone_name(),
    }
    cache_set(cache_key, result, ttl_seconds=60)
    return result
