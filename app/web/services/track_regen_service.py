"""
Логика перегенерации треков по архивным mp4 (batch / single-video).

Вынесено из ``ui_system_routes`` — меньше монолит, проще тесты.
"""
from __future__ import annotations

from app_config.app_config import app_config
from models import Species, Video, VideoSpecies, db
from services.species_registry_service import resolve_species_name


def run_track_regen_with_precise_fallback(
    video_path: str,
    process_video_for_tracks,
    fast_kwargs: dict,
    precise_kwargs_factory=None,
):
    """Быстрый regen; при 0 детекций — второй (точный) проход."""
    detections = process_video_for_tracks(video_path, **fast_kwargs)
    precise_used = False
    if detections or precise_kwargs_factory is None:
        return detections, precise_used
    precise_kwargs = precise_kwargs_factory()
    if not precise_kwargs:
        return detections, precise_used
    precise_used = True
    return process_video_for_tracks(video_path, **precise_kwargs), precise_used


def derive_track_regen_species_scope(start_dt=None) -> list[str]:
    """Scope recovery: виды из БД + mapping."""
    names: set[str] = set()
    mapping = app_config.get('detection.species_mapping') or {}
    for value in mapping.values():
        value = str(value or '').strip()
        if value and value not in {'Unknown', 'Bird'}:
            names.add(value)

    q = (
        db.session.query(Species.name)
        .join(VideoSpecies, VideoSpecies.species_id == Species.id)
        .join(Video, Video.id == VideoSpecies.video_id)
    )
    if start_dt is not None:
        q = q.filter(Video.start_time < start_dt)
    for (name,) in q.distinct().all():
        name = str(name or '').strip()
        if name and name not in {'Unknown', 'Bird'}:
            names.add(name)
    return sorted(names)


def remap_detection_to_local_scope(
    detection: dict,
    local_scope_names_lc: set[str],
) -> dict:
    """Локальные виды оставить; прочие — Unknown (через resolve)."""
    name = str(detection.get('species_name') or '').strip()
    if not name or not local_scope_names_lc:
        return detection
    if name.lower() in local_scope_names_lc:
        return detection
    resolved = resolve_species_name(name, source='ingest')
    if resolved.found and resolved.taxon:
        common = str(resolved.taxon.common_name or '').strip().lower()
        if common and common in local_scope_names_lc:
            return {**detection, 'species_name': resolved.taxon.common_name}
    return {**detection, 'species_name': 'Unknown'}


def summarize_track_regen_detections(detections: list[dict]) -> dict:
    """Сводка для UI после regen одного ролика (в т.ч. tracks_overlay_expected по списку детекций)."""
    reasons: dict[str, int] = {}
    with_frames = 0
    for d in detections:
        r = str(d.get('decision_reason') or 'unknown')
        reasons[r] = reasons.get(r, 0) + 1
        if d.get('frames'):
            with_frames += 1
    return {
        'track_count': len(detections),
        'decision_reasons': reasons,
        'detections_with_frames': with_frames,
        'tracks_overlay_expected': with_frames > 0,
    }
