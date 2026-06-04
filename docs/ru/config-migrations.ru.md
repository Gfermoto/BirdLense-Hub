# Миграции user_config (SOTA-03 / #494)

## Версия схемы

В `user_config.yaml` после миграции появляется блок:

```yaml
_meta:
  schema_version: 2
```

Текущая версия: `USER_CONFIG_SCHEMA_VERSION` в `app/app_config/config_migrations.py`.

При загрузке конфига вызывается `run_user_config_migrations()` (scales, MQTT topics, HA, classifier path, motion→triggers, **track-first v2**: opencv в triggers, `persist_mode`, `tuning_role` на известных камерах).

## Аудит

`GET /api/ui/system/config-audit` — deprecated и unknown keys (см. `app_config/deprecated_keys.py`).

## Сохранение настроек

`PATCH /api/ui/settings` при наличии deprecated keys в raw YAML добавляет в ответ:

```json
{
  "_settings_warnings": {
    "deprecated_keys_present": ["weather.ha_url", "..."]
  }
}
```

UI (Настройки) показывает предупреждение после успешного сохранения. Ключ `_settings_warnings` не попадает в GET settings (фильтруется в `prepare_settings_for_api`).
