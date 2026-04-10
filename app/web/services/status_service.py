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


def check_video_reachable() -> str:
    """
    Проверка доступности камер через go2rtc snapshot.
    Returns: 'ok' | 'error' | 'not_configured'
    """
    go2rtc_url = (os.environ.get('GO2RTC_URL') or app_config.get('video.go2rtc_url') or '').strip()
    cameras_config = app_config.get('video.cameras') or []
    valid = get_valid_cameras(cameras_config)
    if not go2rtc_url or not valid:
        return 'not_configured'
    stream_name = valid[0].get('stream_name') or valid[0].get('id', '')
    if not stream_name:
        return 'not_configured'
    base = go2rtc_url.rstrip('/')
    url = f'{base}/api/frame.jpeg?src={stream_name}'
    username = os.environ.get('GO2RTC_USERNAME') or app_config.get('video.go2rtc_username')
    password = os.environ.get('GO2RTC_PASSWORD') or app_config.get('video.go2rtc_password')
    auth = (username, password) if (username and password) else None
    try:
        r = requests.get(url, auth=auth, timeout=5)
        return 'ok' if r.status_code == 200 else 'error'
    except Exception as e:
        logger.debug('Video check failed: %s', e)
        return 'error'


def parse_yolo_status_from_heartbeat(heartbeat_data: dict | None) -> str:
    """
    Из данных heartbeat процессора: yolo_ok при последнем успешном run в пределах 5 мин.
    Returns: 'ok' | 'unknown'
    """
    if not heartbeat_data:
        return 'unknown'
    last_ok = heartbeat_data.get('last_yolo_ok_at')
    if not last_ok:
        return 'unknown'
    try:
        dt = datetime.fromisoformat(last_ok.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if (now - dt).total_seconds() <= STATUS_FRESH_SECONDS:
            return 'ok'
    except (TypeError, ValueError):
        pass
    return 'unknown'
