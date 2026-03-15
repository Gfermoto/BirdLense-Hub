# Глубокое ревью кодовой базы BirdLense Hub

**Дата:** 15 марта 2026

---

## 1. Баги и упущения

### 1.1 Потенциальные баги

| Проблема | Файл | Описание |
|----------|------|----------|
| **`datetime.now()` без timezone** | `ui_routes.py:297, 362` | Локальное время сравнивается с UTC в БД. Нужно `datetime.now(timezone.utc)` |
| **`logger.warn` устарел** | `visit_processor.py:103` | В Python 3 удалён, использовать `logger.warning` |
| **`request.json` без проверки** | `ui_system_routes.py:181` | При `request.json is None` → `AttributeError`. Нужно `request.json or {}` |
| **Валидация `species_id`** | `ui_routes.py:576` | Может быть строка или не int. Нужна явная проверка типа |

### 1.2 Race conditions

- **Глобальный статус регенерации** (`ui_system_routes.py`): `_regenerate_status`, `_regenerate_tracks_status` — одновременные запросы перезаписывают результат
- **Автозапуск регенерации при scan** — конфликт с ручным запуском

### 1.3 Безопасность

- **Path traversal** в `detection_crop_service` — низкий риск (путь из БД, проверка в processor_routes)
- **SQL injection** — не обнаружено (ORM)
- **XSS** — не обнаружено

---

## 2. Неточности и несоответствия

- **API.md** не описывает `/api/ui/dataset/export`, `/api/ui/push/*`
- **MQTT статус** `unknown` не описан в документации
- **Дублирование** логики timeline в `get_video_species` и `get_species_summary`
- **Парсинг дат** — повторяется паттерн `datetime.fromtimestamp(int(param), timezone.utc).replace(tzinfo=None)` в 5+ местах

---

## 3. Code smells

| Проблема | Пример |
|----------|--------|
| Длинные функции | `get_overview` ~80 строк, `get_species_summary` ~150 строк |
| Магические числа | `45`, `500`, `200`, `0.5` — вынести в константы/конфиг |
| God module | `ui_routes.py` ~1250 строк — разделить на overview, timeline, species, settings |
| Дублирование | `visit.video_species[0].video if visit.video_species else None` — вынести в хелпер |

---

## 4. Устаревшее

- `logger.warn` → `logger.warning`
- PyYAML, Flask, React — версии актуальные
- `@mui/lab` в beta — учитывать при обновлениях

---

## 5. Архитектура

- **Routes → DB напрямую** — нет сервисного слоя (OverviewService, TimelineService)
- **Конфигурация** разбросана: app_config, env, config.py — описать приоритет
- **Тесты** не покрывают: processor_routes, ui_system_routes, граничные случаи

---

## Приоритеты исправлений

| Приоритет | Проблема | Действие |
|-----------|----------|----------|
| **Высокий** | `datetime.now()` в Overview | `datetime.now(timezone.utc)` |
| **Высокий** | `logger.warn` | `logger.warning` |
| **Высокий** | `request.json` в purge_storage | `request.json or {}` |
| **Средний** | Race при регенерации | Блокировать повторный запуск |
| **Средний** | Валидация `species_id` | Проверка типа, приведение к int |
| **Низкий** | Дублирование timeline | Общая функция |
| **Низкий** | Длинные функции | Разбить get_overview, get_species_summary |
| **Низкий** | Path traversal в crop | Проверка формата video_path |

---

*Отчёт сгенерирован на основе анализа кодовой базы.*
