"""JPEG кроп детекции для GET /api/ui/detections/:id/crop (#293)."""
from __future__ import annotations

from datetime import timedelta

from services.detection_crop_service import crop_filename, extract_detection_frame
from util import ensure_utc


def get_detection_crop_jpeg_and_filename(session, detection_id: int):
    """(jpeg_bytes, filename) или (None, None, error_dict)."""
    from models import VideoSpecies

    vs = session.get(VideoSpecies, detection_id)
    if not vs:
        return None, None, {'error': 'Detection not found'}
    if vs.source != 'video':
        return None, None, {'error': 'Crop only for video detections'}
    video = vs.video
    if not video:
        return None, None, {'error': 'Video not found'}
    offset = vs.start_time + (vs.end_time - vs.start_time) / 2
    jpeg_bytes = extract_detection_frame(video.video_path, offset)
    if not jpeg_bytes:
        return None, None, {'error': 'Failed to extract frame'}
    video_start = ensure_utc(video.start_time)
    det_time = video_start + timedelta(seconds=vs.start_time)
    filename = crop_filename(vs.species.name, det_time.isoformat())
    return jpeg_bytes, filename, None
