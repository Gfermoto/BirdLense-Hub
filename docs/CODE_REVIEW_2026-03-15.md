# Code Review: BirdLense Hub

**Дата:** 15 марта 2026  
**Версия:** 0.1.5

---

## 1. Безопасность

### 1.1 SQL Injection
**Оценка: низкий риск**

- Используется SQLAlchemy ORM, параметры передаются через ORM.
- Единственный raw SQL — миграция в `app/web/app.py:49`.
- Пользовательский ввод в SQL не подставляется.

### 1.2 XSS
**Оценка: низкий риск**

- В UI не используется `dangerouslySetInnerHTML`, `innerHTML`, `eval()`.
- React по умолчанию экранирует вывод.

### 1.3 Path Traversal
**Оценка: частично закрыто**

- `video_path` проверяется regex в `processor_routes.py` и `detection_crop_service.py`.
- `image_path` в `util.py:494,541,549` приходит от processor и используется без проверки.
- **Рекомендация:** проверять, что `image_path` находится внутри разрешённой директории.

### 1.4 Секреты в коде
**Оценка: средний риск**

- `app/web/config.py`: `SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'birdlense-settings-session')`
- Дефолтный `SECRET_KEY` предсказуем — возможна подделка сессии.
- **Рекомендация:** в production требовать `FLASK_SECRET_KEY` из env и не использовать fallback.

### 1.5 Валидация входных данных

- `get_activity` в `ui_system_routes.py`: `strptime(month, '%Y-%m')` без try/except — невалидный `month` приведёт к 500.
- **Рекомендация:** обернуть в try/except.

- `processor_routes.py`: `fromisoformat(data.get('start_time'))` без проверки `None`.
- **Рекомендация:** явно проверять наличие и формат `start_time`/`end_time`.

---

## 2. Ошибки и edge cases

### 2.1 None / null

- `util.py:373` — Wikipedia API: `list(data.get("query", {}).get("pages", {}).values())[0]` — при пустом `pages` будет `IndexError`.
- **Рекомендация:** проверять `pages` перед доступом.

### 2.2 Таймауты

- `requests.get/post` — таймауты заданы (10–15 с).
- `subprocess.run` в `detection_crop_service.py` — `timeout=15`.
- `_fire_webhook` — `timeout=5`.

### 2.3 Race conditions

- `ui_system_routes.py` — блокировки для фоновых задач (`_regenerate_lock`).
- Стоит проверить все пути доступа к `_regenerate_status`.

---

## 3. Code smells

### 3.1 Дублирование

- `_run_regenerate_spectrograms` и `_run_regenerate_tracks` — похожая структура.
- `ensure_utc` в `util.py` и `_ensure_utc` в `visit_processor.py`.
- **Рекомендация:** вынести общую логику и использовать один `ensure_utc`.

### 3.2 Магические числа

- `lores_size = (640, 640)` в `main.py` и `ui_system_routes.py`.
- **Рекомендация:** вынести в константы/конфиг.

### 3.3 Длинные функции

- `register_routes` в `ui_routes.py` — ~800 строк, 40+ вложенных функций.
- **Рекомендация:** разбить на модули по доменам.

### 3.4 util.py — смешанная ответственность

- Смешаны: погода, уведомления, иерархия видов, recordings, Wikipedia.
- **Рекомендация:** разделить на `weather.py`, `notifications.py`, `hierarchy.py`.

---

## 4. Производительность

### 4.1 N+1 запросы

- Timeline: в `format_visit_for_timeline` для каждого `visit` обращаются к `visit.video_species` и `vs.video`.
- **Рекомендация:** использовать `joinedload(SpeciesVisit.video_species).joinedload(VideoSpecies.video)`.

- `get_primary_video_for_visit` в цикле `export_timeline` — отдельный запрос на каждый visit.
- **Рекомендация:** eager load или один запрос с джойнами.

### 4.2 Кэширование

- `filter_feeder_species` каждый раз делает `Species.query.all()`.
- **Рекомендация:** кэшировать результат (TTL или инвалидация при изменении видов).

### 4.3 Тяжёлые операции

- `visit_processor.py`: `update_species_info_from_wiki(species)` для каждой детекции.
- **Рекомендация:** кэшировать или вызывать только для новых видов.

---

## 5. Тестируемость

- `create_app()` создаёт зависимости напрямую.
- **Рекомендация:** внедрять зависимости через аргументы для упрощения тестов.

- `AppConfig` — глобальный синглтон.
- **Рекомендация:** возможность передавать конфиг в `create_app()` для тестов.

---

## 6. Документация и типизация

- Многие route-функции в `ui_routes.py` без docstrings.
- `util.py`: `get_primary_video_for_visit(visit) -> object | None` — лучше `Video | None`.
- UI: `{ target: { value: any } }` — заменить на `string`.

---

## Сводная таблица приоритетов

| Категория | Критичность | Файлы |
|-----------|-------------|-------|
| SECRET_KEY по умолчанию | Высокая | `config.py` |
| Валидация `image_path` | Средняя | `util.py` |
| Wikipedia `pages` IndexError | Средняя | `util.py` |
| `get_activity` без try/except | Средняя | `ui_system_routes.py` |
| N+1 в timeline/export | Средняя | `ui_routes.py`, `util.py` |
| Разбить `ui_routes.py` | Низкая | `ui_routes.py` |
| Разделить `util.py` | Низкая | `util.py` |
| Кэш `filter_feeder_species` | Низкая | `util.py` |

---

## Рекомендуемый порядок работ

1. Убрать дефолтный `SECRET_KEY` в production.
2. Добавить валидацию `image_path` в `notify()`.
3. Обработать пустой `pages` в Wikipedia API.
4. Обернуть `get_activity` в try/except.
5. Добавить eager loading для timeline/export.
6. Рефакторинг `ui_routes.py` и `util.py`.
