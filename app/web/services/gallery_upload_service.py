"""Публичная галерея: opt-in загрузка лучших кадров на общий сайт сообщества."""
import logging
import os
from datetime import datetime, timezone

import requests

from app_config.app_config import app_config
from services.detection_crop_service import (
    _bbox_for_offset,
    extract_detection_frame_cropped,
)

logger = logging.getLogger(__name__)


def _get_location_metadata():
    """Координаты из настроек для метаданных."""
    lat = app_config.get('secrets.latitude') or '39.8283'
    lon = app_config.get('secrets.longitude') or '-98.5795'
    return {'latitude': lat, 'longitude': lon}


def _upload_video_species_to_gallery(vs, video, species_name: str) -> bool:
    """
    Извлечь crop детекции и загрузить на gallery.upload_url.
    Returns True if upload succeeded.
    """
    if vs.source != 'video' or not vs.frames:
        return False
    offset = vs.start_time + (vs.end_time - vs.start_time) / 2
    bbox = _bbox_for_offset(getattr(vs, 'frames', None), offset)
    if not bbox:
        return False
    jpeg_bytes = extract_detection_frame_cropped(video.video_path, offset, bbox)
    if not jpeg_bytes:
        return False

    upload_url = (app_config.get('gallery.upload_url') or '').strip()
    if not upload_url:
        return False

    detection_time = video.start_time
    if hasattr(detection_time, 'replace'):
        if detection_time.tzinfo is None:
            detection_time = detection_time.replace(tzinfo=timezone.utc)
        time_iso = detection_time.isoformat()
    else:
        time_iso = str(detection_time)

    files = {'image': ('crop.jpg', jpeg_bytes, 'image/jpeg')}
    data = {
        'species': species_name,
        'confidence': str(vs.confidence),
        'timestamp': time_iso,
        'detection_id': str(vs.id),
        'video_id': str(video.id),
        **_get_location_metadata(),
    }

    try:
        r = requests.post(
            upload_url,
            files=files,
            data=data,
            timeout=30,
        )
        if r.status_code == 200:
            logger.info("Gallery upload: %s (vs %s)", species_name, vs.id)
            return True
        logger.warning("Gallery upload failed %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("Gallery upload error: %s", e)
    return False


def upload_video_detections_to_gallery(video_id: int):
    """
    Загрузить все подходящие детекции видео в галерею.
    Вызывается в отдельном потоке после create_video.
    """
    if not app_config.get('gallery.enabled'):
        return
    upload_url = (app_config.get('gallery.upload_url') or '').strip()
    if not upload_url:
        return

    min_conf = float(app_config.get('gallery.min_confidence') or 0.5)
    only_corrected = app_config.get('gallery.only_manually_corrected') or False

    from models import Video, VideoSpecies

    video = Video.query.get(video_id)
    if not video or not video.video_path:
        return

    q = VideoSpecies.query.filter(
        VideoSpecies.video_id == video_id,
        VideoSpecies.source == 'video',
        VideoSpecies.confidence >= min_conf,
        VideoSpecies.frames.isnot(None),
    )
    if only_corrected:
        q = q.filter(VideoSpecies.manually_corrected == True)

    for vs in q.all():
        species_name = vs.species.name if vs.species else 'Unknown'
        _upload_video_species_to_gallery(vs, video, species_name)
