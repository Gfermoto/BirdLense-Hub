"""Последний вес с весов (MQTT → файл в DATA_DIR или сущность Home Assistant)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import requests

from app_config.app_config import app_config

logger = logging.getLogger(__name__)

FEEDER_SCALE_STATE_FILE = 'feeder_scale_state.json'


def _data_dir() -> str:
    return os.environ.get('DATA_DIR') or os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')),
        'data',
    )


def _read_scale_file() -> dict | None:
    path = os.path.join(_data_dir(), FEEDER_SCALE_STATE_FILE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.debug('feeder scale file: %s', e)
        return None


def _fetch_ha_scale(entity_id: str) -> dict | None:
    ha_url = (
        os.environ.get('HA_URL') or app_config.get('weather.ha_url') or ''
    ).strip().rstrip('/')
    token = (
        os.environ.get('HA_TOKEN') or app_config.get('weather.ha_token') or ''
    ).strip()
    if not ha_url or not token or not entity_id:
        return None
    url = f'{ha_url}/api/states/{entity_id}'
    try:
        r = requests.get(
            url,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            timeout=5,
        )
        r.raise_for_status()
        body = r.json()
        state = body.get('state')
        if state in (None, 'unknown', 'unavailable'):
            return None
        val = float(str(state).replace(',', '.'))
        attrs = body.get('attributes') or {}
        unit = attrs.get('unit_of_measurement') or app_config.get(
            'integrations.scales.unit'
        ) or 'kg'
        unit = str(unit).strip().lower()[:8] or 'kg'
        return {
            'weight': val,
            'unit': unit,
            'updated_at': body.get('last_changed')
            or datetime.now(timezone.utc).isoformat(),
            'source': 'homeassistant',
        }
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.debug('HA scale fetch: %s', e)
        return None


def get_feeder_scale_snapshot() -> dict | None:
    """{ weight, unit, updated_at, source? } или None."""
    if not app_config.get('integrations.scales.enabled'):
        return None
    src = (app_config.get('integrations.scales.source') or 'mqtt').strip().lower()
    if src == 'homeassistant':
        eid = (app_config.get('integrations.scales.homeassistant_entity_id') or '').strip()
        return _fetch_ha_scale(eid)
    raw = _read_scale_file()
    if not raw:
        return None
    try:
        w = float(raw.get('weight'))
    except (TypeError, ValueError):
        return None
    return {
        'weight': w,
        'unit': str(raw.get('unit') or 'kg').lower()[:8],
        'updated_at': raw.get('updated_at'),
        'source': 'mqtt',
    }
