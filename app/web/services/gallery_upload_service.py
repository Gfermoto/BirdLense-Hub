"""Публичная галерея: opt-in загрузка лучших кадров на общий сайт сообщества."""
import logging
from datetime import timezone

import requests

from app_config.app_config import app_config
from services.detection_crop_service import (
    _bbox_for_offset,
    extract_detection_frame_cropped_or_full,
)

logger = logging.getLogger(__name__)


def _normalize_jpeg_for_gallery(jpeg_bytes: bytes) -> bytes:
    """Same constraints as Telegram: min edge, reasonable size — community-facing images."""
    if not jpeg_bytes:
        return jpeg_bytes
    max_side = 1280
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(jpeg_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        w, h = img.size
        if min(w, h) < 64:
            ratio = 64 / float(min(w, h))
            img = img.resize(
                (max(64, int(w * ratio)), max(64, int(h * ratio))),
                Image.Resampling.LANCZOS,
            )
            w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / float(max(w, h))
            img = img.resize(
                (max(1, int(w * ratio)), max(1, int(h * ratio))),
                Image.Resampling.LANCZOS,
            )
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=88, optimize=True)
        return buf.getvalue()
    except Exception as e:
        logger.debug("Gallery JPEG normalize (PIL) failed: %s", e)
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return jpeg_bytes
        h, w = img.shape[:2]
        if min(h, w) < 64:
            ratio = 64.0 / float(min(h, w))
            img = cv2.resize(
                img,
                (max(64, int(w * ratio)), max(64, int(h * ratio))),
                interpolation=cv2.INTER_CUBIC,
            )
            h, w = img.shape[:2]
        if max(w, h) > max_side:
            ratio = max_side / float(max(w, h))
            img = cv2.resize(
                img,
                (max(1, int(w * ratio)), max(1, int(h * ratio))),
                interpolation=cv2.INTER_AREA,
            )
        ok, enc = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        return enc.tobytes() if ok else jpeg_bytes
    except Exception as e:
        logger.debug("Gallery JPEG normalize (cv2) failed: %s", e)
    return jpeg_bytes


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
    jpeg_bytes = extract_detection_frame_cropped_or_full(video.video_path, offset, bbox)
    if not jpeg_bytes:
        return False
    jpeg_bytes = _normalize_jpeg_for_gallery(jpeg_bytes)
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
        if r.status_code in (200, 201, 204):
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

    from models import Video, VideoSpecies, db

    video = db.session.get(Video, video_id)
    if not video or not video.video_path:
        return

    q = VideoSpecies.query.filter(
        VideoSpecies.video_id == video_id,
        VideoSpecies.source == 'video',
        VideoSpecies.confidence >= min_conf,
        VideoSpecies.frames.isnot(None),
    )
    if only_corrected:
        q = q.filter(VideoSpecies.manually_corrected.is_(True))

    rows = q.all()
    if not rows:
        logger.info(
            "Gallery: video %s — нет строк для загрузки (нужны source=video, frames в БД, "
            "confidence>=%s%s). Визиты в UI могут быть и с audio-детекций.",
            video_id,
            min_conf,
            "; только manually_corrected" if only_corrected else "",
        )
        return

    for vs in rows:
        species_name = vs.species.name if vs.species else 'Unknown'
        _upload_video_species_to_gallery(vs, video, species_name)
