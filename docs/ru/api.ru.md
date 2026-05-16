# API BirdLense Hub

[English](../contributor/api.md)

---

**Версия:** совпадает с корневым файлом `VERSION` в репозитории (то же значение, что в `app/web/openapi.yaml`).

Полная спецификация: [OpenAPI YAML](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/openapi.yaml).

**Интерактивно в браузере:** [OpenAPI (Redoc)](../../archive/internal/docs-legacy/reference/openapi.ru.md).

## Группы эндпоинтов

### UI API (`/api/ui/*`)

Пути в таблице — суффикс после `/api/ui` (например `/health` → `GET /api/ui/health`).

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Проверка доступности |
| `/readiness` | GET | Готовность хаба: БД, каталоги на запись, проверки компонентов — **200** при `"ready": true`, **503** с телом JSON при неготовности (балансировщики / `verify-stack`) |
| `/status` | GET | Статус компонентов (web, processor, mqtt, esphome, yolo). Значения: ok, error, not_configured, not_used, unknown |
| `/cameras` | GET | Список камер |
| `/weather` | GET | Погода |
| `/timeline` | GET | Визиты по периоду (params: start_time, end_time) |
| `/timeline/export` | GET | Экспорт визитов в CSV, JSON или eBird (params: start_time, end_time, format=csv\|json\|ebird) |
| `/videos/:id` | GET | Детали видео |
| `/videos/:id/neighbors` | GET | Предыдущее/следующее видео; поддерживает локальный день и переход на соседние сутки через `day_scope`, `tz_offset_minutes`, `cross_day`, в ответе `day_scope`, `day_label`, `timezone_offset_minutes` |
| `/overview` | GET | Данные для Overview |
| `/species` | GET | Список видов |
| `/birdfood` | GET/POST | Список и добавление корма |
| `/birdfood/:id/toggle` | PATCH | Переключить активность корма |
| `/bird_families` | GET | Список семейств птиц |
| `/feed/dispense` | POST | Выдать корм |
| `/settings` | GET/PATCH | Настройки |
| `/settings/requires-password` | GET | Проверка, требуется ли пароль |
| `/settings/verify-password` | POST | Разблокировка (`password` → `role`). **401** при неверном пароле; **429** + `Retry-After` после 5 неудач за 60 с на IP — см. [ACCESS_CONTROL](./access-control.ru.md) |
| `/settings/check-access` | GET | Состояние сессии: `{ unlocked, role? }` — всегда **200** (заблокировано → `unlocked: false`; без лишнего 403 в консоли браузера) |
| `/unknowns` | GET | Детекции с низкой confidence (params: start_time, end_time, limit) |
| `/region-comparison` | GET | Сравнение видов с топом eBird региона (требует secrets.ebird_api_key) |
| `/detections/:id` | PATCH | Исправить вид детекции (body: `{species_id}`). Требует пароль настроек |
| `/detections/:id/crop` | GET | Кадр из видео для экспорта в iNaturalist. Возвращает JPEG |
| `/dataset/export` | GET | Экспорт датасета (ZIP: train/val + dataset_info.json). Требует пароль |
| `/push/vapid-public` | GET | Публичный ключ VAPID для Web Push подписки |
| `/push/subscribe` | POST | Регистрация Web Push подписки (body: `{subscription}`) |
| `/report/pdf` | GET | Месячный PDF-отчёт (params: month=YYYY-MM или start_time, end_time) |
| `/migration-calendar` | GET | Агрегация визитов по виду и месяцу. Параметры: `catalog`=`observed`\|`dataset`\|`full_eu` (legacy: `active`→`observed`, `full`→`full_eu`); опционально `start_year`/`end_year` или `start_date`/`end_date` (`YYYY-MM-DD`). Параметр `evidence` принимается для совместимости, но **игнорируется** (ответ одинаковый). |
| `/species/:id/xeno-canto` | GET | Записи птичьих песен из Xeno-canto для вида |
| `/species/:id/summary` | GET | Сводка по виду |
| `/restart-processor` | POST | Перезапуск processor |

### Prometheus

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/metrics` | GET | Prometheus: CPU, память, диск, GPU, detections, species, videos |
| `/api/metrics` | GET | То же (для Grafana) |
| `/api/metrics/summary` | GET | JSON-сводка метрик для дашбордов и observability-checks |

См. [CONFIGURATION](./configuration.ru.md) — раздел Prometheus / Grafana.

### System API (`/api/ui/system/*`)

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/system/metrics` | GET | Мгновенный снимок: CPU, память, диск, GPU (`encoding` — подсказка для графика GPU) |
| `/system/metrics/history` | GET | Временной ряд для графиков (`?hours=`, `?max_points=`), снимки в SQLite |
| `/system/visitors` | GET | Уникальные сессии посетителей за `?days=` (агрегат SpeciesVisit) |
| `/system/activity` | GET | Активность по дням |
| `/storage/stats` | GET | Статистика записей |
| `/storage/purge` | POST | Удаление записей: `{"date"}` — всё до этой даты включительно; или `{"start_date","end_date"}` — календарный диапазон включительно |
| `/system/retention` | POST | Запуск политики retention |
| `/system/regenerate-spectrograms` | POST | Регенерация спектрограмм |
| `/system/regenerate-spectrograms/status` | GET | Статус регенерации спектрограмм |
| `/system/regenerate-tracks/status` | GET | Статус регенерации треков |
| `/system/recordings/scan` | POST | Сканирование и импорт записей |
| `/system/logs` | GET | Логи процессора (последние N строк, ?lines=100) |

### Реестр видов (`/api/ui/system/species-registry/*`)

**Админ** (разблокированная сессия настроек). Детали тел и ответов — **`app/web/openapi.yaml`**.

| Путь | Метод | Описание |
|------|-------|----------|
| `/system/species-registry/seed` | POST | Заполнить реестр и алиасы из встроенного mapping |
| `/system/species-registry/backfill` | POST | Привязка видов к taxa; JSON `dry_run` (по умолчанию true), опционально `limit` |
| `/system/species-registry/unresolved` | GET | Топ неразрешённых имён (`?limit=`) |
| `/system/species-registry/enrich-metadata/start` | POST | Старт async обогащения метаданных → **202** / **409** |
| `/system/species-registry/enrich-metadata/status` | GET | Статус задачи обогащения |
| `/system/species-registry/health` | GET | Метрики здоровья / покрытия реестра |
| `/system/species-registry/materialize-allowlist` | POST | Создать недостающие строки allowlist (`dry_run`, `fill_metadata`, `limit`) |
| `/system/species-registry/repair-cards/start` | POST | Ремонт карточек видов → **202** / **409** |
| `/system/species-registry/repair-cards/status` | GET | Статус ремонта + покрытие |
| `/system/species-registry/data-quality` | GET | Отчёт о качестве каталога (`?duplicate_limit=`) |
| `/system/species-registry/classifier-dataset-alignment` | GET | Классификатор vs БД vs папки датасета |
| `/system/species-registry/coverage-metrics` | GET | Сегменты покрытия |
| `/system/species-registry/tuning-targets/export` | GET | Экспорт tuning targets: `format=json` (по умолчанию) или `format=csv` |

Остальные системные эндпоинты — см. `ui_system_*.py` и OpenAPI.

### Processor API (`/api/processor/*`)

Внутренний API для processor. Защищён `X-Processor-Token` при заданном `PROCESSOR_SECRET`.

В **`app/web/openapi.yaml`** выберите сервер **`…/api/processor`**; пути ниже — относительно этой базы (не под `/api/ui`).

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/videos` | POST | Создание записи с детекциями |
| `/species/active` | PUT | Установка активных видов |
| `/notify/detections` | POST | Уведомление о детекции |
| `/notify/motion` | POST | Уведомление о движении |
| `/activity_log` | POST | Heartbeat, статус processor |

## Аутентификация

- **По умолчанию** — нет. Доступ ко всем эндпоинтам открыт.
- **Настройки** — опционально `settings_password` в конфиге. При заданном пароле `/settings`, `/storage/purge`, `/restart-processor` и др. требуют разблокировки через `verify-password`.
- **MCP** — опционально `MCP_TOKEN` в env. Заголовок `Authorization: Bearer <token>`.
- **Processor API** — опционально `PROCESSOR_SECRET` в env. Заголовок `X-Processor-Token`.

## Примечание по UI-маршрутам

- Legacy-маршрут **`/unknowns`** сохранён для закладок и редиректит на **`/timeline?review=1`**.
- Режим «На проверке» использует тот же API неизвестных (`GET /api/ui/unknowns`), а обычный режим Timeline — `GET /api/ui/timeline`.

---

См. также: [CONFIGURATION](./configuration.ru.md), [ARCHITECTURE](./architecture.ru.md), [ACCESS_CONTROL](./access-control.ru.md), [GLOSSARY](./glossary.ru.md).
