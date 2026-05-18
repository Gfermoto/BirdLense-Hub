"""Сериализация видео для GET /api/ui/videos/:id и detection-frames (#293)."""

from __future__ import annotations

import json
from datetime import timezone

from typing import Any

from services.feeder_scale import video_scales_estimate_payload


def _species_row(vs) -> dict:
    data = {
        "id": vs.id,
        "species_id": vs.species.id,
        "species_name": vs.species.name,
        "start_time": vs.start_time,
        "end_time": vs.end_time,
        "confidence": vs.confidence,
        "source": vs.source,
        "track_id": vs.track_id,
        "image_url": vs.species.image_url,
        "individual_nickname": vs.individual_nickname,
        "bird_profile_id": vs.bird_profile_id,
        "bird_profile_name": (vs.bird_profile.display_name if getattr(vs, "bird_profile", None) else None),
        "bird_profile_avatar_url": (vs.bird_profile.avatar_url if getattr(vs, "bird_profile", None) else None),
        "bird_profile_status": (vs.bird_profile.status if getattr(vs, "bird_profile", None) else None),
        "classifier_needs_review": bool(getattr(vs, "classifier_needs_review", False)),
        "review_reason": getattr(vs, "review_reason", None),
    }
    if vs.detection_provider:
        data["detection_provider"] = vs.detection_provider
    return data


def build_video_detail_dict(video) -> dict:
    """Ожидаются joinedload video_species→species и food."""
    out: dict[str, Any] = {
        "id": video.id,
        "created_at": video.created_at.astimezone(timezone.utc).isoformat(),
        "processor_version": video.processor_version,
        "start_time": video.start_time.astimezone(timezone.utc).isoformat(),
        "end_time": video.end_time.astimezone(timezone.utc).isoformat(),
        "video_path": video.video_path,
        "spectrogram_path": video.spectrogram_path,
        "favorite": video.favorite,
        "weather": {
            "main": video.weather_main,
            "description": video.weather_description,
            "temp": video.weather_temp,
            "humidity": video.weather_humidity,
            "pressure": video.weather_pressure,
            "clouds": video.weather_clouds,
            "wind_speed": video.weather_wind_speed,
        },
        "species": [_species_row(vs) for vs in video.video_species],
        "food": [{"id": bf.id, "name": bf.name, "image_url": bf.image_url} for bf in video.food],
        "scales": video_scales_estimate_payload(video),
    }
    bl = getattr(video, "behavior_label", None)
    if bl:
        out["behavior_label"] = str(bl).strip()
    bc = getattr(video, "behavior_confidence", None)
    if bc is not None:
        try:
            out["behavior_confidence"] = round(float(bc), 6)
        except (TypeError, ValueError):
            pass
    mk = getattr(video, "behavior_model_kind", None)
    if mk:
        out["behavior_model_kind"] = str(mk).strip()
    mv = getattr(video, "behavior_model_version", None)
    if mv:
        out["behavior_model_version"] = str(mv).strip()
    sh = getattr(video, "behavior_shadow_label", None)
    if sh:
        out["behavior_shadow_label"] = str(sh).strip()
    shc = getattr(video, "behavior_shadow_confidence", None)
    if shc is not None:
        try:
            out["behavior_shadow_confidence"] = round(float(shc), 6)
        except (TypeError, ValueError):
            pass
    shk = getattr(video, "behavior_shadow_model_kind", None)
    if shk:
        out["behavior_shadow_model_kind"] = str(shk).strip()
    shv = getattr(video, "behavior_shadow_model_version", None)
    if shv:
        out["behavior_shadow_model_version"] = str(shv).strip()
    return out


def build_video_detection_frames_dict(video) -> dict:
    """Ожидается joinedload video_species."""
    tracks = []
    for vs in video.video_species:
        if not vs.frames:
            continue
        try:
            frames = json.loads(vs.frames)
        except (TypeError, ValueError):
            continue
        tracks.append(
            {
                "id": vs.id,
                "species_id": vs.species_id,
                "start_time": vs.start_time,
                "end_time": vs.end_time,
                "frames": frames,
            }
        )
    return {"tracks": tracks}
