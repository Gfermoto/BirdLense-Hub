import copy
import logging
import os
import shutil
from datetime import datetime

import yaml

logger = logging.getLogger(__name__)

# Ключи с секретами — маскируются в API, не перезаписываются при сохранении placeholder
SENSITIVE_KEYS = frozenset({
    'performance.redis_url',
    'general.settings_password',
    'general.contributor_password',
    'notifications.telegram_bot_token',
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

        # Merge configs (user_config overrides default_config)
        return self.merge_dicts(default_config, user_config)

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

    def save(self, filename=None):
        save_file = filename or self.user_config_file
        if os.path.exists(save_file):
            bak = f'{save_file}.bak'
            try:
                shutil.copy2(save_file, bak)
            except OSError as e:
                logger.warning('Could not create backup %s: %s', bak, e)
        with open(save_file, 'w') as file:
            yaml.safe_dump(self.config, file)


app_config = AppConfig()
