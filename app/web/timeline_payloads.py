"""SpeciesVisit / Video JSON for /api/ui/timeline (#222 — вынесено из util.py)."""

from __future__ import annotations

from datetime import timedelta, datetime, timezone

from species_constants import GENERIC_BIRD_SPECIES
from time_util import ensure_utc

from services.feeder_scale import video_scales_estimate_payload


def get_primary_video_for_visit(visit) -> object | None:
    """Deterministically pick the earliest video for a SpeciesVisit."""
    return get_primary_video_for_visit_in_window(visit)


def get_primary_video_for_visit_in_window(
    visit,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> object | None:
    """Pick the earliest visit video, optionally constrained to a time window."""
    if not visit or not getattr(visit, 'video_species', None):
        return None
    vs_list = [
        vs for vs in visit.video_species
        if getattr(vs, 'video', None) and getattr(vs.video, 'start_time', None)
    ]
    if window_start is not None or window_end is not None:
        window_start_utc = (
            ensure_utc(window_start) if window_start is not None else None
        )
        window_end_utc = (
            ensure_utc(window_end) if window_end is not None else None
        )
        filtered_vs = []
        for vs in vs_list:
            video_start = ensure_utc(vs.video.start_time)
            video_end = ensure_utc(vs.video.end_time)
            if window_start_utc is not None and video_end <= window_start_utc:
                continue
            if window_end_utc is not None and video_start >= window_end_utc:
                continue
            filtered_vs.append(vs)
        vs_list = filtered_vs
    if not vs_list:
        return None
    primary = min(
        vs_list,
        key=lambda vs: (
            ensure_utc(vs.video.start_time),
            getattr(vs.video, 'id', 0) or 0,
        ),
    )
    return primary.video


def format_visit_for_timeline(visit) -> dict:
    """Format SpeciesVisit to timeline API format (detections, weather, species)."""
    video = get_primary_video_for_visit(visit)
    video_duration_seconds = None
    if video:
        v0 = ensure_utc(video.start_time)
        v1 = ensure_utc(video.end_time)
        video_duration_seconds = max(0, round((v1 - v0).total_seconds()))
    detections = []
    total_recording_seconds = 0.0
    for vs in sorted(visit.video_species, key=lambda x: x.created_at, reverse=True):
        video_start = ensure_utc(vs.video.start_time)
        seg_dur = max(0, vs.end_time - vs.start_time) if vs.end_time > vs.start_time else 0
        total_recording_seconds += seg_dur
        det = {
            'id': vs.id,
            'video_id': vs.video_id,
            'start_time': (video_start + timedelta(seconds=vs.start_time)).astimezone(timezone.utc).isoformat(),
            'end_time': (video_start + timedelta(seconds=vs.end_time)).astimezone(timezone.utc).isoformat(),
            'confidence': vs.confidence,
            'source': vs.source,
        }
        if vs.detection_provider:
            det['detection_provider'] = vs.detection_provider
        detections.append(det)
    return {
        'id': visit.id,
        'start_time': ensure_utc(visit.start_time).isoformat(),
        'end_time': ensure_utc(visit.end_time).isoformat(),
        'max_simultaneous': visit.max_simultaneous,
        'total_recording_seconds': round(total_recording_seconds),
        'video_duration_seconds': video_duration_seconds,
        'weather': {
            'temp': video.weather_temp if video else None,
            'clouds': video.weather_clouds if video else None,
        } if video else None,
        'scales': video_scales_estimate_payload(video) if video else None,
        'species': {
            'id': visit.species.id,
            'name': visit.species.name,
            'image_url': visit.species.image_url,
            'parent_id': visit.species.parent_id,
        },
        'detections': detections,
        'timeline_kind': 'visit',
    }


def format_unlinked_video_for_timeline(video, *, fallback_species) -> dict:
    """Ролик за интервал без привязки к SpeciesVisit — тот же контракт, что у визита в /timeline."""
    v0 = ensure_utc(video.start_time)
    v1 = ensure_utc(video.end_time)
    video_duration_seconds = max(0, round((v1 - v0).total_seconds()))
    detections = []
    total_recording_seconds = 0.0
    vss = sorted(video.video_species, key=lambda x: x.created_at, reverse=True)
    for vs in vss:
        video_start = ensure_utc(vs.video.start_time)
        seg_dur = max(0, vs.end_time - vs.start_time) if vs.end_time > vs.start_time else 0
        total_recording_seconds += seg_dur
        det = {
            'id': vs.id,
            'video_id': vs.video_id,
            'start_time': (video_start + timedelta(seconds=vs.start_time)).astimezone(timezone.utc).isoformat(),
            'end_time': (video_start + timedelta(seconds=vs.end_time)).astimezone(timezone.utc).isoformat(),
            'confidence': vs.confidence,
            'source': vs.source,
        }
        if vs.detection_provider:
            det['detection_provider'] = vs.detection_provider
        detections.append(det)
    if vss:
        sp = vss[0].species
        species_block = {
            'id': sp.id,
            'name': sp.name,
            'image_url': sp.image_url,
            'parent_id': sp.parent_id,
        }
    elif fallback_species is not None:
        species_block = {
            'id': fallback_species.id,
            'name': fallback_species.name,
            'image_url': fallback_species.image_url,
            'parent_id': fallback_species.parent_id,
        }
    else:
        species_block = {
            'id': 0,
            'name': GENERIC_BIRD_SPECIES,
            'image_url': None,
            'parent_id': None,
        }
    if not detections:
        detections.append({
            'video_id': video.id,
            'start_time': v0.astimezone(timezone.utc).isoformat(),
            'end_time': v1.astimezone(timezone.utc).isoformat(),
            'confidence': 0.0,
            'source': 'video',
        })
    return {
        'id': -(video.id),
        'start_time': v0.isoformat(),
        'end_time': v1.isoformat(),
        'max_simultaneous': 1,
        'total_recording_seconds': round(total_recording_seconds) if total_recording_seconds else video_duration_seconds,
        'video_duration_seconds': video_duration_seconds,
        'weather': {
            'temp': video.weather_temp,
            'clouds': video.weather_clouds,
        },
        'scales': video_scales_estimate_payload(video),
        'species': species_block,
        'detections': detections,
        'timeline_kind': 'unlinked_video',
    }
