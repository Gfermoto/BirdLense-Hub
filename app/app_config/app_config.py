import copy
import logging
import os
import shutil
from datetime import datetime

import yaml

logger = logging.getLogger(__name__)

CONFIDENCE_FLOORS = {
    'detection.min_confidence_to_store': 0.30,
    'processor.min_confidence_to_process': 0.30,
    'processor.min_confidence_to_notify': 0.30,
    'processor.min_confidence_binary': 0.22,
    'processor.min_track_duration': 1.0,
    'processor.min_box_size_px': 64,
}

# Ключи с секретами — маскируются в API, не перезаписываются при сохранении placeholder
SENSITIVE_KEYS = frozenset({
    'homeassistant.token',
    'performance.redis_url',
    'general.settings_password',
    'general.contributor_password',
    'notifications.telegram_bot_token',
    'notifications.telegram_mtproto_secret',
    'notifications.telegram_api_hash',
    'web_push.vapid_private_key',
    'mqtt.password',
    'video.go2rtc_password',
    'weather.ha_token',
    'secrets.openweather_api_key',
    'secrets.xeno_canto_api_key',
    'secrets.ebird_api_key',
    'mcp.token',
})
MASK_PLACEHOLDER = '***'


def migrate_legacy_homeassistant_from_weather(user_config: dict) -> bool:
    """Переносит weather.ha_url / weather.ha_token в homeassistant.* и удаляет устаревшие ключи.

    Возвращает True, если user_config изменён (нужно сохранить файл).
    """
    if not isinstance(user_config, dict):
        return False
    weather = user_config.get('weather')
    if not isinstance(weather, dict):
        return False
    if 'ha_url' not in weather and 'ha_token' not in weather:
        return False

    def _non_empty(val) -> bool:
        return bool(str(val or '').strip())

    changed = False
    ha = user_config.get('homeassistant')
    if not isinstance(ha, dict):
        ha = {}
        user_config['homeassistant'] = ha
        changed = True

    for leg_key, ha_key in (('ha_url', 'url'), ('ha_token', 'token')):
        if leg_key not in weather:
            continue
        leg_val = weather[leg_key]
        if not _non_empty(leg_val):
            del weather[leg_key]
            changed = True
            continue
        cur = ha.get(ha_key)
        if not _non_empty(cur) and _non_empty(leg_val):
            ha[ha_key] = leg_val
            changed = True
        cur = ha.get(ha_key)
        if _non_empty(cur) and leg_key in weather:
            del weather[leg_key]
            changed = True

    return changed


class AppConfig:
    def __init__(self, user_config='user_config.yaml', default_config='default_config.yaml'):
        self.user_config_file = f"{os.path.dirname(__file__)}/{user_config}"
        self.default_config_file = f"{os.path.dirname(__file__)}/{default_config}"
        self.config = self.load_and_merge_configs()

    def reload(self):
        """Reload config from disk (e.g. after external edit or to pick up saved keys)."""
        self.config = self.load_and_merge_configs()

    def load_and_merge_configs(self):
        # Load default config
        if not os.path.exists(self.default_config_file):
            raise FileNotFoundError(
                f"Default configuration file {self.default_config_file} not found."
            )

        try:
            with open(self.default_config_file, 'r') as file:
                default_config = yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            logger.error("Invalid YAML in %s: %s", self.default_config_file, e)
            default_config = {}

        user_config = {}
        if os.path.exists(self.user_config_file):
            try:
                with open(self.user_config_file, 'r') as file:
                    user_config = yaml.safe_load(file) or {}
            except yaml.YAMLError as e:
                logger.error("Invalid YAML in %s: %s", self.user_config_file, e)
            if migrate_legacy_homeassistant_from_weather(user_config):
                try:
                    self._persist_raw_user_config(user_config)
                    logger.info(
                        'Migrated weather.ha_url / weather.ha_token to homeassistant.* in %s',
                        self.user_config_file,
                    )
                except OSError as e:
                    logger.warning('Could not persist HA legacy key migration: %s', e)

        # Merge configs (user_config overrides default_config)
        merged = self.merge_dicts(default_config, user_config)
        self._enforce_confidence_floors(merged)
        return merged

    @staticmethod
    def merge_dicts(base, overrides):
        """Recursively merge overrides into base; returns new dict, does not mutate base."""
        result = copy.copy(base)
        for key, value in overrides.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = AppConfig.merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _coerce_float(value, fallback):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    @classmethod
    def _enforce_confidence_floors(cls, config):
        """Clamp stale low-confidence settings to safe minimums."""
        changed = False
        for path, floor in CONFIDENCE_FLOORS.items():
            current = cls._get_nested(config, path)
            if current is None:
                continue
            coerced = cls._coerce_float(current, floor)
            if coerced < floor:
                cls._set_nested(config, path, floor)
                changed = True
        if changed:
            logger.warning(
                'Clamped legacy low confidence settings to safe floors: %s',
                ', '.join(f'{key}>={value}' for key, value in CONFIDENCE_FLOORS.items()),
            )
        return changed

    @staticmethod
    def _mask_value(val):
        """Маскирует непустое значение."""
        if val is None or (isinstance(val, str) and not val.strip()):
            return val
        return MASK_PLACEHOLDER

    @staticmethod
    def _get_nested(d, path):
        """Получить значение по пути 'a.b.c'."""
        for k in path.split('.'):
            d = (d or {}).get(k)
        return d

    @staticmethod
    def _set_nested(d, path, value):
        """Установить значение по пути 'a.b.c'."""
        keys = path.split('.')
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    @classmethod
    def mask_config_for_api(cls, config):
        """Возвращает копию конфига с замаскированными секретами."""
        out = copy.deepcopy(config)
        for path in SENSITIVE_KEYS:
            val = cls._get_nested(out, path)
            if val is not None:
                cls._set_nested(out, path, cls._mask_value(val))
        return out

    @classmethod
    def prepare_settings_for_api(cls, config):
        """Копия для GET/PATCH settings: HA URL/токен только в homeassistant.*; legacy weather.ha_* скрыты."""
        out = copy.deepcopy(config)
        weather = out.get('weather') or {}
        ha = out.setdefault('homeassistant', {})
        if not str(ha.get('url') or '').strip() and weather.get('ha_url'):
            ha['url'] = weather['ha_url']
        if not str(ha.get('token') or '').strip() and weather.get('ha_token'):
            ha['token'] = weather['ha_token']
        w = out.get('weather')
        if isinstance(w, dict):
            w.pop('ha_url', None)
            w.pop('ha_token', None)
        return cls.mask_config_for_api(out)

    @classmethod
    def filter_sensitive_placeholders(cls, updates):
        """Не перезаписывать секреты placeholder'ами (***) или пустой строкой."""
        out = copy.deepcopy(updates)
        for path in SENSITIVE_KEYS:
            val = cls._get_nested(out, path)
            if val is None:
                continue
            if isinstance(val, str) and (val.strip() == MASK_PLACEHOLDER or not val.strip()):
                cls._remove_nested(out, path)
        return out

    @staticmethod
    def _remove_nested(d, path):
        """Удалить ключ по пути 'a.b.c' из updates."""
        keys = path.split('.')
        parent = d
        for k in keys[:-1]:
            parent = parent.get(k)
            if parent is None:
                return
        if isinstance(parent, dict) and keys[-1] in parent:
            del parent[keys[-1]]

    def get(self, key, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            value = value.get(k, default)
            if value is None:
                return default
        return value

    def set(self, key, value):
        keys = key.split('.')
        config_section = self.config
        for k in keys[:-1]:
            config_section = config_section.setdefault(k, {})
        config_section[keys[-1]] = value
        self._enforce_confidence_floors(self.config)

    def _persist_raw_user_config(self, data: dict) -> None:
        """Записать сырой user YAML (для миграции ключей без полного self.config)."""
        save_file = self.user_config_file
        if os.path.exists(save_file):
            bak = f'{save_file}.bak'
            try:
                shutil.copy2(save_file, bak)
            except OSError as e:
                logger.warning('Could not create backup %s: %s', bak, e)
        with open(save_file, 'w', encoding='utf-8') as file:
            yaml.safe_dump(data, file, allow_unicode=True)

    def save(self, filename=None):
        save_file = filename or self.user_config_file
        self._enforce_confidence_floors(self.config)
        if os.path.exists(save_file):
            bak = f'{save_file}.bak'
            try:
                shutil.copy2(save_file, bak)
            except OSError as e:
                logger.warning('Could not create backup %s: %s', bak, e)
        with open(save_file, 'w') as file:
            yaml.safe_dump(self.config, file)


app_config = AppConfig()
