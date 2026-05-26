# Схема конфигурации (Pydantic / JSON Schema)

SOTA-01 (#492): валидация объединённого конфига (`default_config.yaml` + `user_config.yaml`) при загрузке и перед сохранением настроек из UI.

## Где в коде

| Компонент | Путь |
|-----------|------|
| Pydantic-модели | `app/app_config/config_schema.py` |
| JSON Schema (генерация) | `app/app_config/schema/birdlense_config.schema.json` |
| Интеграция при merge | `app/app_config/app_config.py` → `load_and_merge_configs` |
| PATCH настроек | `app/web/services/settings_patch_service.py` |

## Секции с типизацией

- `general`, `detection`, `video`, `processor`, `species`, `mqtt`

Неизвестные ключи внутри секций **разрешены** (`extra='allow'`) — обратная совместимость с полным YAML.

## Переменные окружения

| Переменная | Значение |
|------------|----------|
| `BIRDLENSE_PYDANTIC_CONFIG_VALIDATE` | `1` (по умолчанию) — Pydantic-валидация; `0` — выкл. |
| `BIRDLENSE_STRICT_CONFIG` | `1` — падение при любой ошибке структуры/семантики/Pydantic |

## Экспорт JSON Schema

```bash
cd app && PYTHONPATH=web:. python3 ../scripts/export_config_schema.py
```

## Тесты

```bash
cd app/web && PYTHONPATH=.:.. python3 -m pytest tests/test_config_pydantic_schema.py -q
```
