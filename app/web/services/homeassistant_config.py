"""Единая точка URL и Long-Lived Token Home Assistant (погода, весы и др.)."""
from __future__ import annotations

import os

from app_config.app_config import app_config


def get_homeassistant_url() -> str:
    """HA_URL в env, затем homeassistant.url, затем legacy weather.ha_url."""
    for v in (
        os.environ.get('HA_URL'),
        app_config.get('homeassistant.url'),
        app_config.get('weather.ha_url'),
    ):
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s.rstrip('/')
    return ''


def get_homeassistant_token() -> str:
    """HA_TOKEN в env, затем homeassistant.token, затем legacy weather.ha_token."""
    for v in (
        os.environ.get('HA_TOKEN'),
        app_config.get('homeassistant.token'),
        app_config.get('weather.ha_token'),
    ):
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ''
