"""Extract a single frame from video for iNaturalist export."""
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

INATURALIST_UPLOAD_URL = "https://www.inaturalist.org/observations/upload"

# Path traversal: only allow DB format data/recordings/YYYY/MM/DD/timestamp/video.mp4
VIDEO_PATH_SAFE_RE = re.compile(r'^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/video\.mp4$')


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
    if not video_path or not VIDEO_PATH_SAFE_RE.match(video_path):
        logger.warning("Rejected invalid video_path format")
        return None
    from util import full_path_for_video
    full_path = full_path_for_video(video_path)
    if not full_path or not os.path.isfile(full_path):
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
