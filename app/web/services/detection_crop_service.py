"""Extract a single frame from video for iNaturalist export."""
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

INATURALIST_UPLOAD_URL = "https://www.inaturalist.org/observations/upload"


def _app_base_for_video_path():
    """Base dir for video_path from DB (data/recordings/YYYY/MM/DD/...). Returns app root."""
    data_dir = os.environ.get(
        'DATA_DIR',
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data')
    )
    return os.path.dirname(data_dir)


def _safe_filename(name: str) -> str:
    """Replace unsafe chars for filename."""
    return re.sub(r'[^\w\s\-\(\)]', '_', name).strip().replace(' ', '_')


def extract_detection_frame(video_path: str, offset_sec: float) -> bytes | None:
    """
    Extract a single JPEG frame from video at given offset.
    video_path: from DB, e.g. "data/recordings/2024/03/15/123456/video.mp4"
    offset_sec: seconds from video start
    Returns JPEG bytes or None on failure.
    """
    base = _app_base_for_video_path()
    full_path = os.path.join(base, video_path) if not os.path.isabs(video_path) else video_path
    if not os.path.isfile(full_path):
        logger.warning(f"Video not found: {full_path}")
        return None
    try:
        # -ss before -i: fast seek (no full decode)
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-ss', str(offset_sec),
            '-i', full_path,
            '-vframes', '1',
            '-q:v', '2',
            '-f', 'image2', 'pipe:1'
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        if result.returncode != 0:
            logger.warning(f"ffmpeg failed: {result.stderr.decode()[:200]}")
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg timeout extracting frame")
        return None
    except Exception as e:
        logger.exception("Frame extraction failed: %s", e)
        return None


def crop_filename(species_name: str, start_time_str: str) -> str:
    """Generate filename for iNaturalist: Species_Name_YYYY-MM-DD_HHMMSS.jpg"""
    # start_time_str is ISO like "2024-03-15T14:32:00+00:00"
    safe_name = _safe_filename(species_name)
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        date_part = dt.strftime('%Y-%m-%d')
        time_part = dt.strftime('%H%M%S')
        return f"{safe_name}_{date_part}_{time_part}.jpg"
    except Exception:
        return f"{safe_name}.jpg"
