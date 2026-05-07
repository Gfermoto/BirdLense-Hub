"""Extract a single frame from video for iNaturalist export."""

import logging
import os
import re
import subprocess

from shared.detection_crop_contract import bbox_for_offset

logger = logging.getLogger(__name__)

INATURALIST_UPLOAD_URL = "https://www.inaturalist.org/observations/upload"

# Path traversal: only allow DB format data/recordings/YYYY/MM/DD/timestamp/video.mp4
VIDEO_PATH_SAFE_RE = re.compile(r"^data/recordings/\d{4}/\d{2}/\d{2}/[\d\-:]+/video\.mp4$")


def _safe_filename(name: str) -> str:
    """Replace unsafe chars for filename."""
    return re.sub(r"[^\w\s\-\(\)]", "_", name).strip().replace(" ", "_")


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
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(offset_sec),
            "-i",
            full_path,
            "-vframes",
            "1",
            "-q:v",
            "2",
            "-f",
            "image2",
            "pipe:1",
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


def _bbox_for_offset(frames_json: str | None, offset_sec: float) -> list[float] | None:
    """
    Find bbox from frames JSON closest to offset_sec.
    frames: [{t: float, bbox: [x1,y1,x2,y2]}, ...] — bbox normalized 0–1.
    Returns [x1,y1,x2,y2] or None.
    """
    return bbox_for_offset(frames_json, offset_sec)


def extract_detection_frame_cropped(video_path: str, offset_sec: float, bbox_norm: list[float] | None) -> bytes | None:
    """
    Extract frame and crop by normalized bbox [x1,y1,x2,y2] (0–1).
    If bbox_norm is None or invalid, returns None (never full frame — dataset must contain only crops).
    """
    jpeg_bytes = extract_detection_frame(video_path, offset_sec)
    if not jpeg_bytes or not bbox_norm or len(bbox_norm) != 4:
        return None
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        x1 = int(bbox_norm[0] * w)
        y1 = int(bbox_norm[1] * h)
        x2 = int(bbox_norm[2] * w)
        y2 = int(bbox_norm[3] * h)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = img[y1:y2, x1:x2]
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return buf.tobytes() if ok and buf is not None else None
    except Exception as e:
        logger.warning("Crop failed, skipping (no full-frame fallback): %s", e)
        return None


def extract_detection_frame_cropped_or_full(
    video_path: str, offset_sec: float, bbox_norm: list[float] | None
) -> bytes | None:
    """
    Prefer bbox crop; if crop fails or bbox missing, return full JPEG frame at offset (community uploads).
    """
    cropped = extract_detection_frame_cropped(video_path, offset_sec, bbox_norm)
    if cropped:
        return cropped
    return extract_detection_frame(video_path, offset_sec)


def crop_filename(species_name: str, start_time_str: str) -> str:
    """Generate filename for iNaturalist: Species_Name_YYYY-MM-DD_HHMMSS.jpg"""
    # start_time_str is ISO like "2024-03-15T14:32:00+00:00"
    safe_name = _safe_filename(species_name)
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        date_part = dt.strftime("%Y-%m-%d")
        time_part = dt.strftime("%H%M%S")
        return f"{safe_name}_{date_part}_{time_part}.jpg"
    except (TypeError, ValueError) as exc:
        logger.debug("crop_filename iso parse failed: %s", exc, exc_info=True)
        return f"{safe_name}.jpg"
