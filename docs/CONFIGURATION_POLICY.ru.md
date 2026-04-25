# Политика конфигурации

[English](./CONFIGURATION_POLICY.md)

Этот документ фиксирует слой политики для конфигурации BirdLense Hub. Справочник
ключей остаётся в [CONFIGURATION](./CONFIGURATION.ru.md).

## Источники правды

| Источник | За что отвечает | Где живёт | Примечания |
| --- | --- | --- | --- |
| `app/app_config/default_config.yaml` | Поставляемые defaults и форма ключей | Git | Новые non-breaking defaults начинаются здесь. |
| `app/app_config/user_config.yaml` | Локальные override оператора | Runtime-файл, не коммитится | Рекурсивно накладывается на defaults. Отсутствующий ключ берёт default; пустая строка — значение. |
| `app/.env.example` и env деплоя | Секреты и runtime-only параметры | Env хоста/контейнера | `BIRDLENSE_*` overlay заменяет merged config в памяти без записи в YAML. |
| `app/web/config.py` | Flask/SQLAlchemy/CORS настройки процесса | Python config из env | Валидируется при импорте/старте там, где небезопасен silent default. |
| `app/web/routes/ui_settings_routes.py` + `services/settings_patch_service.py` | Mutating Settings API | Пишет `user_config.yaml` через `AppConfig.save()` | PATCH обязан валидировать merged candidate до сохранения. |
| `app/processor/src/*` | Runtime-потребители | Читает merged config из `app_config` | Processor не должен вводить новые shape без default и docs. |

## Приоритет

1. Загружается `default_config.yaml`.
2. Загружается и рекурсивно мержится `user_config.yaml`.
3. Применяются миграции legacy user keys, если есть безопасное автоматическое
   соответствие.
4. Применяются runtime secret/env overlays.
5. Валидируется shape объединённого конфига.

Путь web Settings PATCH валидирует candidate merged config до записи. Пример
ошибки для оператора:

```json
{
  "error": "Validation failed",
  "issues": ["top-level key 'mqtt' must be a mapping or null, got str"]
}
```

## Политика валидации

- Отклонять top-level секции, которые не mapping и не `null`.
- Отклонять mutating API payload до записи `user_config.yaml`.
- Startup validation по умолчанию мягкая для старых установок; для fail-fast есть
  `BIRDLENSE_STRICT_CONFIG=1`.
- Семантическую валидацию добавлять инкрементально для рискованных ключей:
  секреты, processor thresholds, storage paths, внешние URLs.

## Совместимость

- Non-breaking: добавить ключ с default, принять legacy alias, расширить enum,
  зажать старый небезопасный threshold с warning.
- Breaking: удалить ключ, изменить тип, сузить enum, поменять default-поведение
  для уже сохранённого YAML.
- Breaking change требует release notes и, где возможно, миграцию в
  `app/app_config/app_config.py`.
- Deprecated keys читаются минимум один release cycle, если они не создают риск
  безопасности или потери данных.
