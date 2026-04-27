"""Каталог избранных роликов: группировка по видам без календарного окна."""

from __future__ import annotations

from datetime import timezone

from sqlalchemy.orm import joinedload

from models import Video, VideoSpecies
from services.feeder_scale import video_scales_estimate_payload


def _iso_utc(dt) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _species_payload(vs: VideoSpecies) -> dict:
    return {
        "id": vs.species.id,
        "name": vs.species.name,
        "image_url": vs.species.image_url,
        "confidence": vs.confidence,
        "start_time": vs.start_time,
        "end_time": vs.end_time,
        "source": vs.source,
    }


def _video_payload(video: Video) -> dict:
    return {
        "id": video.id,
        "start_time": _iso_utc(video.start_time),
        "end_time": _iso_utc(video.end_time),
        "video_path": video.video_path,
        "favorite": bool(video.favorite),
        "deleted": video.deleted_at is not None,
        "duration_seconds": max(0.0, (video.end_time - video.start_time).total_seconds()),
        "species": [_species_payload(vs) for vs in video.video_species if vs.species is not None],
        "scales": video_scales_estimate_payload(video),
    }


def _species_group_payload(species, videos: list[Video]) -> dict:
    ordered = sorted(videos, key=lambda v: (v.start_time, v.id or 0), reverse=True)
    return {
        "species": {
            "id": species.id,
            "name": species.name,
            "image_url": species.image_url,
            "parent_id": species.parent_id,
        },
        "count": len(ordered),
        "latest_start_time": _iso_utc(ordered[0].start_time),
        "videos": [_video_payload(video) for video in ordered],
    }


def build_favorites_by_species_payload(session) -> dict:
    """Все активные favorite-видео, сгруппированные по видам; без привязки к дате."""
    videos = (
        session.query(Video)
        .options(
            joinedload(Video.video_species).joinedload(VideoSpecies.species),
            joinedload(Video.food),
        )
        .filter(Video.favorite.is_(True), Video.deleted_at.is_(None))
        .order_by(Video.start_time.desc(), Video.id.desc())
        .all()
    )

    by_species: dict[int, tuple[object, list[Video]]] = {}
    unclassified: list[Video] = []
    for video in videos:
        seen_species: set[int] = set()
        for vs in video.video_species:
            species = vs.species
            if species is None or species.id in seen_species:
                continue
            seen_species.add(species.id)
            bucket = by_species.setdefault(species.id, (species, []))
            bucket[1].append(video)
        if not seen_species:
            unclassified.append(video)

    groups = [_species_group_payload(species, bucket) for species, bucket in by_species.values()]
    groups.sort(key=lambda g: (g["latest_start_time"], g["species"]["name"]), reverse=True)

    unclassified.sort(key=lambda v: (v.start_time, v.id or 0), reverse=True)
    return {
        "total_videos": len(videos),
        "total_species": len(groups),
        "groups": groups,
        "unclassified": {
            "count": len(unclassified),
            "videos": [_video_payload(video) for video in unclassified],
        },
    }
