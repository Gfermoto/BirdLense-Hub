import copy
import logging
import os
import shutil

import yaml

from app_config.secret_env import apply_secret_env_overrides
from app_config.config_schema import validate_merged_config_pydantic
from app_config.trigger_config import (
    build_motion_settings_mirror_for_api,
    copy_legacy_topic_if_missing,
    fold_legacy_motion_out_of_merged_config,
    migrate_legacy_motion_block,
)

logger = logging.getLogger(__name__)

# Минимумы ниже считаются «сломанными» пост-миграциями из старых джобов YAML.
# Слишком жёсткие полы (1.0s / 0.30 confidence) режут ByteTrack-треки, которые реально есть.
# detection.min_confidence_to_store должно быть <= processor.min_confidence_to_process для согласованного fusion.
CONFIDENCE_FLOORS = {
    "detection.min_confidence_to_store": 0.08,
    "processor.min_confidence_to_process": 0.20,
    "processor.min_confidence_to_notify": 0.28,
    "processor.min_confidence_binary": 0.08,
    "processor.min_track_duration": 0.25,
    # Small-object / distant scenes: keep floor usable without site-specific camera hacks.
    "processor.min_box_size_px": 12,
}

# Ключи с секретами — маскируются в API, не перезаписываются при сохранении placeholder
SENSITIVE_KEYS = frozenset(
    {
        "homeassistant.token",
        "performance.redis_url",
        "general.settings_password",
        "general.contributor_password",
        "notifications.telegram_bot_token",
        "notifications.telegram_mtproto_secret",
        "notifications.telegram_api_hash",
        "web_push.vapid_private_key",
        "mqtt.password",
        "video.go2rtc_password",
        "weather.ha_token",
        "secrets.openweather_api_key",
        "secrets.xeno_canto_api_key",
        "secrets.ebird_api_key",
        "mcp.token",
        "storage.recordings_mirror.sftp_password",
        "storage.recordings_mirror.sftp_key_passphrase",
    }
)

# Только админ (при двух паролях): оператор не может менять даже реальными значениями
CONTRIBUTOR_ADMIN_ONLY_PATCH_PATHS = frozenset(
    {
        "general.settings_password",
        "general.contributor_password",
        "general.session_idle_minutes",
        "mcp.token",
        "storage.recordings_mirror",
    }
)
MASK_PLACEHOLDER = "***"

# Верхнеуровневые секции YAML: при ошибке типа (строка вместо mapping) ломается .get по вложенным ключам.
_CONFIG_TOP_LEVEL_MAPPING_KEYS = frozenset(
    {
        "camera",
        "detection",
        "ebird",
        "feed",
        "general",
        "homeassistant",
        "integrations",
        "mcp",
        "mqtt",
        "motion",
        "notifications",
        "performance",
        "processor",
        "secrets",
        "species",
        "storage",
        "triggers",
        "video",
        "weather",
        "web_push",
    }
)


def validate_merged_config(merged: dict) -> list[str]:
    """Проверка структуры объединённого конфига после merge default + user.

    Возвращает список сообщений об ошибках; пустой список — ок.
    Не проверяет семантику значений (порты, URL) — только типы верхнего уровня.
    """
    issues: list[str] = []
    if not isinstance(merged, dict):
        return ["config root must be a mapping (dict), not %s" % type(merged).__name__]
    for key in sorted(_CONFIG_TOP_LEVEL_MAPPING_KEYS & set(merged.keys())):
        val = merged.get(key)
        if val is not None and not isinstance(val, dict):
            issues.append(
                "top-level key %r must be a mapping or null, got %s" % (key, type(val).__name__),
            )
    return issues


def _semantic_float_or_issue(
    merged: dict,
    path: str,
    label: str,
    issues: list[str],
) -> float | None:
    """Разобрать float по dotted path; при невалидном типе — сообщение в issues."""
    raw = AppConfig._get_nested(merged, path)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        issues.append("%s (%s) must be numeric, got %r" % (label, path, raw))
        return None


def validate_merged_config_semantics(merged: dict) -> list[str]:
    """Семантические инварианты merged-конфига (после floors/cleanup как при старте).

    Сейчас: detection.min_confidence_to_store ≤ processor.min_confidence_to_process.
    """
    issues: list[str] = []
    if not isinstance(merged, dict):
        return issues
    store = _semantic_float_or_issue(
        merged,
        "detection.min_confidence_to_store",
        "detection.min_confidence_to_store",
        issues,
    )
    proc = _semantic_float_or_issue(
        merged,
        "processor.min_confidence_to_process",
        "processor.min_confidence_to_process",
        issues,
    )
    if store is not None and proc is not None and store > proc + 1e-9:
        issues.append(
            "detection.min_confidence_to_store (%s) must be <= "
            "processor.min_confidence_to_process (%s) for consistent fusion" % (store, proc),
        )
    proc_root = merged.get("processor")
    if isinstance(proc_root, dict):
        br = proc_root.get("behavior_recognition")
        if isinstance(br, dict):
            for path, label in (
                (
                    "processor.behavior_recognition.confidence_store_min",
                    "processor.behavior_recognition.confidence_store_min",
                ),
                (
                    "processor.behavior_recognition.confidence_review_threshold",
                    "processor.behavior_recognition.confidence_review_threshold",
                ),
            ):
                v = _semantic_float_or_issue(merged, path, label, issues)
                if v is not None and (v < 0.0 or v > 1.0 + 1e-9):
                    issues.append("%s must be between 0 and 1, got %s" % (label, v))
            raw_md = br.get("max_runtime_detections")
            if raw_md is not None:
                try:
                    md_i = int(raw_md)
                    if md_i < 1 or md_i > 500:
                        issues.append(
                            "processor.behavior_recognition.max_runtime_detections must be 1..500, got %s"
                            % (md_i,)
                        )
                except (TypeError, ValueError):
                    issues.append(
                        "processor.behavior_recognition.max_runtime_detections must be int, got %r"
                        % (raw_md,)
                    )
    return issues


def migrate_legacy_homeassistant_from_weather(user_config: dict) -> bool:
    """Переносит weather.ha_url / weather.ha_token в homeassistant.* и удаляет устаревшие ключи.

    Возвращает True, если user_config изменён (нужно сохранить файл).
    """
    if not isinstance(user_config, dict):
        return False
    weather = user_config.get("weather")
    if not isinstance(weather, dict):
        return False
    if "ha_url" not in weather and "ha_token" not in weather:
        return False

    def _non_empty(val) -> bool:
        return bool(str(val or "").strip())

    changed = False
    ha = user_config.get("homeassistant")
    if not isinstance(ha, dict):
        ha = {}
        user_config["homeassistant"] = ha
        changed = True

    for leg_key, ha_key in (("ha_url", "url"), ("ha_token", "token")):
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


def migrate_legacy_scales_source(user_config: dict) -> bool:
    """Нормализует старые значения `integrations.scales.source`."""
    if not isinstance(user_config, dict):
        return False
    integrations = user_config.get("integrations")
    if not isinstance(integrations, dict):
        return False
    scales = integrations.get("scales")
    if not isinstance(scales, dict):
        return False
    changed = False
    src = str(scales.get("source") or "").strip().lower()
    if src == "esphome_mqtt":
        scales["source"] = "mqtt"
        changed = True
    elif src == "esphome_direct":
        scales["source"] = "esphome"
        changed = True

    weight_sensor_id = str(scales.get("esphome_weight_sensor_id") or "").strip()
    if weight_sensor_id == "raw_hx711":
        scales["esphome_weight_sensor_id"] = "weight_live_internal"
        changed = True

    return changed


def migrate_legacy_trigger_topics(user_config: dict) -> bool:
    """Copy legacy MQTT topic locations into the new domain/grouped sections."""
    if not isinstance(user_config, dict):
        return False
    changed = False
    mqtt = user_config.get("mqtt")
    if not isinstance(mqtt, dict):
        return False

    if str(mqtt.get("frigate_topic") or "").strip():
        triggers = user_config.get("triggers")
        if not isinstance(triggers, dict):
            triggers = {}
            user_config["triggers"] = triggers
            changed = True
        frigate = triggers.get("frigate")
        if not isinstance(frigate, dict):
            frigate = {}
            triggers["frigate"] = frigate
            changed = True
        if copy_legacy_topic_if_missing(frigate, "topic", mqtt, "frigate_topic"):
            changed = True

    if str(mqtt.get("birdnet_topic") or "").strip():
        integrations = user_config.get("integrations")
        if not isinstance(integrations, dict):
            integrations = {}
            user_config["integrations"] = integrations
            changed = True
        birdnet = integrations.get("birdnet")
        if not isinstance(birdnet, dict):
            birdnet = {}
            integrations["birdnet"] = birdnet
            changed = True
        if copy_legacy_topic_if_missing(birdnet, "mqtt_topic", mqtt, "birdnet_topic"):
            changed = True

    return changed


def migrate_processor_classifier_best_eu_path(user_config: dict) -> bool:
    """Заменяет ошибочный путь best_EU.pt на канонический best.pt.

    В образе и в HF EU-веса лежат как models/classification/weights/best.pt.
    Старые подсказки UI упоминали best_EU.pt как «пример» — часть user_config
    могла сохраниться с этим именем.
    """
    if not isinstance(user_config, dict):
        return False
    processor = user_config.get("processor")
    if not isinstance(processor, dict):
        return False
    models = processor.get("models")
    if not isinstance(models, dict):
        return False
    cur = models.get("classifier")
    if not isinstance(cur, str):
        return False
    s = cur.strip()
    if not s:
        return False
    canon = "models/classification/weights/best.pt"
    if s == "models/classification/weights/best_EU.pt":
        models["classifier"] = canon
        return True
    if s.replace("\\", "/").endswith("/models/classification/weights/best_EU.pt"):
        models["classifier"] = canon
        return True
    return False


class AppConfig:
    def __init__(self, user_config="user_config.yaml", default_config="default_config.yaml"):
        self.user_config_file = f"{os.path.dirname(__file__)}/{user_config}"
        self.default_config_file = f"{os.path.dirname(__file__)}/{default_config}"
        self.config = self.load_and_merge_configs()

    def reload(self):
        """Reload config from disk (e.g. after external edit or to pick up saved keys)."""
        self.config = self.load_and_merge_configs()

    def load_and_merge_configs(self):
        # Load default config
        if not os.path.exists(self.default_config_file):
            raise FileNotFoundError(f"Default configuration file {self.default_config_file} not found.")

        try:
            with open(self.default_config_file, "r") as file:
                default_config = yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            logger.error("Invalid YAML in %s: %s", self.default_config_file, e)
            default_config = {}

        user_config = {}
        if os.path.exists(self.user_config_file):
            try:
                with open(self.user_config_file, "r") as file:
                    user_config = yaml.safe_load(file) or {}
            except yaml.YAMLError as e:
                logger.error("Invalid YAML in %s: %s", self.user_config_file, e)
            if migrate_legacy_scales_source(user_config):
                try:
                    self._persist_raw_user_config(user_config)
                    logger.info(
                        "Migrated integrations.scales.source legacy values in %s",
                        self.user_config_file,
                    )
                except OSError as e:
                    logger.warning("Could not persist scales source migration: %s", e)
            if migrate_legacy_trigger_topics(user_config):
                try:
                    self._persist_raw_user_config(user_config)
                    logger.info(
                        "Migrated legacy mqtt.frigate_topic / mqtt.birdnet_topic into grouped/domain config in %s",
                        self.user_config_file,
                    )
                except OSError as e:
                    logger.warning("Could not persist trigger topic migration: %s", e)
            if migrate_legacy_homeassistant_from_weather(user_config):
                try:
                    self._persist_raw_user_config(user_config)
                    logger.info(
                        "Migrated weather.ha_url / weather.ha_token to homeassistant.* in %s",
                        self.user_config_file,
                    )
                except OSError as e:
                    logger.warning("Could not persist HA legacy key migration: %s", e)
            if migrate_processor_classifier_best_eu_path(user_config):
                try:
                    self._persist_raw_user_config(user_config)
                    logger.info(
                        "Migrated processor.models.classifier best_EU.pt → best.pt in %s",
                        self.user_config_file,
                    )
                except OSError as e:
                    logger.warning("Could not persist classifier path migration: %s", e)
            if migrate_legacy_motion_block(user_config):
                try:
                    self._persist_raw_user_config(user_config)
                    logger.info(
                        "Persisted motion→triggers migration to %s",
                        self.user_config_file,
                    )
                except OSError as e:
                    logger.warning("Could not persist motion→triggers migration: %s", e)

        # Merge configs (user_config overrides default_config)
        merged = self.merge_dicts(default_config, user_config)
        fold_legacy_motion_out_of_merged_config(merged)
        self._enforce_confidence_floors(merged)
        self._cleanup_legacy_processor_keys(merged)
        apply_secret_env_overrides(merged)
        config_issues = validate_merged_config(merged)
        config_issues.extend(validate_merged_config_semantics(merged))
        config_issues.extend(validate_merged_config_pydantic(merged))
        for msg in config_issues:
            logger.error("Config structure validation: %s", msg)
        strict = (os.environ.get("BIRDLENSE_STRICT_CONFIG") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if strict and config_issues:
            raise ValueError(
                "Invalid merged config (set BIRDLENSE_STRICT_CONFIG=0 or fix YAML): " + "; ".join(config_issues),
            )
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

    @staticmethod
    def _cleanup_legacy_processor_keys(config):
        """Нормализует устаревшие processor-ключи в merged config."""
        if not isinstance(config, dict):
            return
        processor = config.get("processor")
        if not isinstance(processor, dict):
            return
        # Runtime поддерживает только two_stage.
        if processor.get("detection_strategy") != "two_stage":
            processor["detection_strategy"] = "two_stage"
        # Канон Rodent: явный min_confidence_binary_squirrel в merge (обычно из user YAML) перекрывает rodent
        sq_thr = processor.get("min_confidence_binary_squirrel")
        if sq_thr is not None:
            processor["min_confidence_binary_rodent"] = sq_thr
        scope = processor.get("detector_scope")
        if isinstance(scope, list) and scope:
            seen: set[str] = set()
            new_scope: list[str] = []
            for raw in scope:
                s = str(raw or "").strip()
                if not s:
                    continue
                canon = "Rodent" if s.lower() == "squirrel" else s
                key = canon.lower()
                if key not in seen:
                    seen.add(key)
                    new_scope.append(canon)
            processor["detector_scope"] = new_scope
        profiles = processor.get("adaptive_profiles")
        if isinstance(profiles, dict):
            night = profiles.get("night")
            if isinstance(night, dict):
                overrides = night.get("overrides")
                if isinstance(overrides, dict):
                    legacy_r = overrides.get("min_confidence_binary_squirrel")
                    if legacy_r is not None:
                        overrides["min_confidence_binary_rodent"] = legacy_r

    @classmethod
    def _enforce_confidence_floors(cls, config):
        """Clamp stale low-confidence settings to safe minimums."""
        source = str(cls._get_nested(config, "video.source") or "").strip().lower()
        if source == "file":
            logger.info("Skip confidence floors in file mode (test source) to allow low-threshold tuning.")
            return False
        skip = (os.environ.get("BIRDLENSE_SKIP_CONFIDENCE_FLOORS") or "").strip().lower()
        if skip in ("1", "true", "yes", "on"):
            logger.info(
                "Skip confidence floors (BIRDLENSE_SKIP_CONFIDENCE_FLOORS) for site tuning."
            )
            return False
        changed = False
        adjusted: list[str] = []
        for path, floor in CONFIDENCE_FLOORS.items():
            current = cls._get_nested(config, path)
            if current is None:
                continue
            coerced = cls._coerce_float(current, floor)
            if coerced < floor:
                cls._set_nested(config, path, floor)
                changed = True
                adjusted.append(f"{path}: {current!r} -> {floor}")
        if changed:
            logger.warning(
                "Clamped legacy low confidence settings to safe floors: %s",
                "; ".join(adjusted),
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
        for k in path.split("."):
            d = (d or {}).get(k)
        return d

    @staticmethod
    def _set_nested(d, path, value):
        """Установить значение по пути 'a.b.c'."""
        keys = path.split(".")
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
        weather = out.get("weather") or {}
        ha = out.setdefault("homeassistant", {})
        if not str(ha.get("url") or "").strip() and weather.get("ha_url"):
            ha["url"] = weather["ha_url"]
        if not str(ha.get("token") or "").strip() and weather.get("ha_token"):
            ha["token"] = weather["ha_token"]
        w = out.get("weather")
        if isinstance(w, dict):
            w.pop("ha_url", None)
            w.pop("ha_token", None)
        out["motion"] = build_motion_settings_mirror_for_api(out)
        return cls.mask_config_for_api(out)

    @classmethod
    def filter_sensitive_placeholders(cls, updates):
        """Не перезаписывать секреты placeholder'ами (***) или пустой строкой.

        Явный JSON ``null`` для секретного ключа тоже убираем из PATCH: иначе
        ``merge_dicts`` записывает None поверх сохранённого пароля/токена.
        """
        out = copy.deepcopy(updates)
        for path in SENSITIVE_KEYS:
            keys = path.split(".")
            parent = out
            for k in keys[:-1]:
                if not isinstance(parent, dict):
                    parent = None
                    break
                parent = parent.get(k)
                if parent is None:
                    break
            if not isinstance(parent, dict):
                continue
            last = keys[-1]
            if last not in parent:
                continue
            val = parent[last]
            if val is None:
                cls._remove_nested(out, path)
                continue
            if isinstance(val, str) and (val.strip() == MASK_PLACEHOLDER or not val.strip()):
                cls._remove_nested(out, path)
        return out

    @classmethod
    def strip_contributor_admin_only_updates(cls, updates):
        """Убрать из PATCH поля, которые оператор не должен менять (пароли доступа, MCP)."""
        out = copy.deepcopy(updates)
        for path in CONTRIBUTOR_ADMIN_ONLY_PATCH_PATHS:
            cls._remove_nested(out, path)
        return out

    @staticmethod
    def _remove_nested(d, path):
        """Удалить ключ по пути 'a.b.c' из updates."""
        keys = path.split(".")
        parent = d
        for k in keys[:-1]:
            parent = parent.get(k)
            if parent is None:
                return
        if isinstance(parent, dict) and keys[-1] in parent:
            del parent[keys[-1]]

    def get(self, key, default=None):
        keys = key.split(".")
        value = self.config
        for k in keys:
            value = value.get(k, default)
            if value is None:
                return default
        return value

    def set(self, key, value):
        keys = key.split(".")
        config_section = self.config
        for k in keys[:-1]:
            config_section = config_section.setdefault(k, {})
        config_section[keys[-1]] = value
        self._enforce_confidence_floors(self.config)

    def load_raw_user_config_dict(self) -> dict:
        """Содержимое user_config.yaml без merge с default."""
        path = self.user_config_file
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            logger.error("Invalid YAML in %s: %s", path, e)
            return {}

    @classmethod
    def mask_sensitive_in_user_tree(cls, user: dict) -> dict:
        """Копия user-дерева с маскировкой SENSITIVE_KEYS (для безопасного экспорта)."""
        out = copy.deepcopy(user) if isinstance(user, dict) else {}
        for path in SENSITIVE_KEYS:
            if cls._get_nested(out, path) is not None:
                cls._set_nested(out, path, MASK_PLACEHOLDER)
        return out

    def validate_user_config_tree(self, user_dict: dict) -> list[str]:
        """Проверка user-снимка после merge с default (типы + семантика, как при load)."""
        try:
            with open(self.default_config_file, "r", encoding="utf-8") as file:
                default_config = yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            return ["default_config YAML error: %s" % e]
        merged = self.merge_dicts(default_config, user_dict)
        fold_legacy_motion_out_of_merged_config(merged)
        self._enforce_confidence_floors(merged)
        self._cleanup_legacy_processor_keys(merged)
        issues = validate_merged_config(merged)
        issues.extend(validate_merged_config_semantics(merged))
        issues.extend(validate_merged_config_pydantic(merged))
        return issues

    def _persist_raw_user_config(self, data: dict) -> None:
        """Записать сырой user YAML (для миграции ключей без полного self.config)."""
        save_file = self.user_config_file
        if os.path.exists(save_file):
            bak = f"{save_file}.bak"
            try:
                shutil.copy2(save_file, bak)
            except OSError as e:
                logger.warning("Could not create backup %s: %s", bak, e)
        with open(save_file, "w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True)

    def update_retention_config(self, retention: dict) -> dict:
        """Обновить retention в user_config.yaml и перезагрузить конфиг.

        Возвращает актуальную безопасную конфигурацию (как GET /retention).
        """
        raw = self.load_raw_user_config_dict()
        if retention:
            raw.setdefault("retention", {})
            raw["retention"].update(retention)
        self._persist_raw_user_config(raw)
        self.reload()
        rc = self.get("retention", {})
        safe = {
            "mode": rc.get("mode", "cascade"),
            "days": rc.get("days"),
            "max_gb": rc.get("max_gb"),
            "dataset_max_age_days": rc.get("dataset_max_age_days", 0),
            "migration_max_age_days": rc.get(
                "migration_max_age_days",
                0,
            ),
            "protect_favorites": rc.get("protect_favorites", True),
            "min_age_hours": rc.get("min_age_hours", 1),
            "batch_size": rc.get("batch_size", 50),
        }
        try:
            from services.retention_service import _fetch_metrics

            m = _fetch_metrics()
            safe["last_run"] = m.get("retention_last_run")
            safe["last_deleted_count"] = m.get(
                "retention_last_deleted_count",
                0,
            )
            safe["last_freed_bytes"] = m.get("retention_last_freed_bytes", 0)
            safe["last_mode"] = m.get("retention_mode", "cascade")
        except Exception:
            pass
        return safe

    def save(self, filename=None):
        save_file = filename or self.user_config_file
        self._enforce_confidence_floors(self.config)
        if os.path.exists(save_file):
            bak = f"{save_file}.bak"
            try:
                shutil.copy2(save_file, bak)
            except OSError as e:
                logger.warning("Could not create backup %s: %s", bak, e)
        with open(save_file, "w") as file:
            yaml.safe_dump(self.config, file)


app_config = AppConfig()
