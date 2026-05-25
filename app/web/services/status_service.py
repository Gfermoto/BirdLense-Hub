"""Реальные проверки статусов: Video (go2rtc), YOLO (из heartbeat процессора)."""

import logging
import os
from datetime import datetime, timezone

import requests

from app_config.app_config import app_config
from app_config.cameras import get_valid_cameras

logger = logging.getLogger(__name__)

# Свежесть: считаем ok если последний успех был в пределах этого интервала
STATUS_FRESH_SECONDS = 300  # 5 мин

GO2RTC_DEFAULT_BASE = "http://127.0.0.1:1984"


def resolve_go2rtc_base_url() -> str:
    """URL go2rtc для проверок из контейнера (как entrypoint/nginx upstream)."""
    url = (os.environ.get("GO2RTC_URL") or app_config.get("video.go2rtc_url") or "").strip()
    if url:
        return url.rstrip("/")
    return GO2RTC_DEFAULT_BASE


def _go2rtc_auth() -> tuple[str, str] | None:
    username = os.environ.get("GO2RTC_USERNAME") or app_config.get("video.go2rtc_username")
    password = os.environ.get("GO2RTC_PASSWORD") or app_config.get("video.go2rtc_password")
    if username and password:
        return (str(username), str(password))
    return None


def _hub_go2rtc_frame_url(stream_name: str) -> str | None:
    """Тот же путь, что в браузере: nginx /go2rtc → upstream."""
    port = (os.environ.get("BIRDLENSE_PORT") or "8080").strip() or "8080"
    return f"http://127.0.0.1:{port}/go2rtc/api/frame.jpeg?src={stream_name}"


def _probe_frame_url(url: str, auth: tuple[str, str] | None) -> bool:
    try:
        r = requests.get(url, auth=auth, timeout=5)
        return r.status_code == 200
    except Exception as e:
        logger.debug("Video frame probe failed (%s): %s", url, e)
        return False


def check_video_reachable() -> str:
    """
    Проверка доступности камер через go2rtc snapshot.
    Returns: 'ok' | 'error' | 'not_configured'
    """
    cameras_config = app_config.get("video.cameras") or []
    valid = get_valid_cameras(cameras_config)
    if not valid:
        return "not_configured"
    base = resolve_go2rtc_base_url()
    auth = _go2rtc_auth()
    for cam in valid:
        stream_name = (cam.get("stream_name") or cam.get("id") or "").strip()
        if not stream_name:
            continue
        candidates = [
            f"{base}/api/frame.jpeg?src={stream_name}",
            _hub_go2rtc_frame_url(stream_name),
        ]
        for url in candidates:
            if url and _probe_frame_url(url, auth):
                return "ok"
    return "error"


def parse_yolo_status_from_heartbeat(heartbeat_data: dict | None) -> str:
    """
    Из данных heartbeat процессора: yolo_ok при последнем успешном run в пределах 5 мин.
    Returns: 'ok' | 'unknown'
    """
    if not heartbeat_data:
        return "unknown"
    last_ok = heartbeat_data.get("last_yolo_ok_at")
    if not last_ok:
        return "unknown"
    try:
        dt = datetime.fromisoformat(last_ok.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if (now - dt).total_seconds() <= STATUS_FRESH_SECONDS:
            return "ok"
    except (TypeError, ValueError):
        pass
    return "unknown"
