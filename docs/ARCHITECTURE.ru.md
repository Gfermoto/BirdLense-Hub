# Архитектура BirdLense Hub

[English](./ARCHITECTURE.md)

---

## Компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│  Один контейнер (birdlense)                                      │
├─────────────────────────────────────────────────────────────────┤
│  nginx:8080  ──►  /          →  static (React SPA)               │
│                 /api         →  Flask:8000                       │
│                 /mcp, /sse   →  MCP:8001 (если enabled)           │
│                 /processor/live  →  processor:8082 (MJPEG)       │
│                 /go2rtc/*    →  внешний Go2RTC                    │
│                 /data/*     →  /app/data (файлы)                  │
├─────────────────────────────────────────────────────────────────┤
│  gunicorn:8000  →  Flask API (/api/ui: ui_routes + доменные       │
│                     ui_*; ui_system_*; processor_routes)         │
├─────────────────────────────────────────────────────────────────┤
│  MCP:8001 (опционально)  →  FastMCP, tools из OpenAPI            │
├─────────────────────────────────────────────────────────────────┤
│  processor  →  main.py: Go2RTC stream, YOLO, ByteTrack,          │
│                запись видео, FFmpeg спектрограммы, MQTT           │
└─────────────────────────────────────────────────────────────────┘
```

**Порты:** nginx внутри контейнера слушает **8080**; Compose пробрасывает **`BIRDLENSE_PORT`** на хосте (по умолчанию **8085**) → **8080**. Flask (gunicorn) для **`/api`** — **8000** внутри; MCP — **8001**; MJPEG процессора — **8082**; наружу обычно открыт только порт nginx.

### Процессы, порты и сигналы health {#runtime-processes-ports-and-health-signals}

| Процесс | Прослушивание (контейнер) | Роль | Признак «ок» |
| --------- | --------------------------- | ------ | ---------------- |
| **nginx** | `0.0.0.0:8080` | Статика UI, `/api` → gunicorn, `/mcp`, прокси Go2RTC, `/data`, `/processor/live` | HTTP 200 на `/` или `/api/ui/health` через проброшенный порт |
| **gunicorn** | `127.0.0.1:8000` | Flask (`/api/ui/*`, `/api/processor/*`, …) | **`GET /api/ui/health`** → `{"status":"ok"}` — цикл ожидания в `entrypoint.sh` и `healthcheck` в Compose |
| **MCP** (опционально) | `127.0.0.1:8001` | FastMCP streamable HTTP | Только при `mcp.enabled`; nginx — `/mcp` |
| **processor** | MJPEG **8082** (внутренний) | `main.py`: ingest, детекция, запись, MQTT | Отдельного HTTP health в образе нет; логи, UI, **`POST /api/processor/*`** |

**Readiness vs liveness (только web):** **`/api/ui/health`** — дешёлая liveness-проба. **`/api/ui/readiness`** — БД, запись в `data/` и `app_config/`, компоненты; **503**, если не готов (`readiness_service`).

## Потоки данных

### Видео

1. **Go2RTC** (внешний) → RTSP/HLS поток
2. **Processor** подключается к Go2RTC, получает кадры
3. **Триггер** (OpenCV, Frigate, MQTT, ESPHome) → начало записи
4. **Detector** — подтверждение target первого уровня (`Bird | Rodent`)
5. **YOLO classifier** — классификация вида для detector-confirmed треков
6. **ByteTrack** — трекинг и bbox по кадрам
7. **Fusion** — общий post-inference слой: detector/classifier outcome, promotion от Frigate, confidence boosters
8. **Запись** → `data/recordings/YYYY/MM/DD/HHMMSS/video.mp4`
9. **Спектрограмма** → FFmpeg (аудио) + librosa (mel) → `spectrogram_200.jpg`
10. **API** → processor отправляет POST `/api/processor/videos` с fused-детекциями

### Доменные границы времени

BirdLense держит три разные временные сущности:

- **trigger-time** — когда источник движения разбудил сессию;
- **clip-time** — физические границы `Video` / файла `video.mp4`;
- **visit-time** — логическое окно присутствия вида после дедупликации.

Подробный контракт и инварианты: [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.ru.md).

### Видео: Frigate (опционально)

1. **Frigate** → публикует в MQTT `frigate/events` (детекция + Bird Classification)
2. **Bird Classification** — `classification.bird.enabled: true` в Frigate, добавляет `sub_label` с видом (INat)
3. **Processor** использует Frigate как helper source: `sub_label`/`label` могут продвинуть generic detector fallback или поднять confidence, но сами по себе не создают persisted video detection

### Аудио (BirdNET)

1. **BirdNET-Pi/Go** (внешний) → публикует в MQTT топик `birdnet`
2. **Processor** (MQTTEventAggregator) подписан на топик
3. BirdNET влияет только на confidence/threshold bias и не создаёт финальный video label

**Европейские птицы:** EU-модель (YOLO11n-cls, ~491 вид) активна в `best.pt`. US (NABirds) — резерв в `best_US.pt`. Frigate и BirdNET теперь вспомогательные источники вокруг общего fusion path, а не равноправные авторы итогового label.

### UI

1. **React SPA** → `index.html`, static assets
2. **API** → `/api/ui/*` (health, status, timeline, timeline/export, videos, unknowns, detections/:id/crop, report/pdf, species/:id/xeno-canto, settings, birdfood и др.)
3. **Метрики** → `GET /metrics`, `GET /api/metrics` (Prometheus)
4. **Видео** → `/data/recordings/...` (nginx alias)
5. **Live** → `/processor/live` (MJPEG от processor) или `/go2rtc/stream.html`

**Модули Flask (`app/web/routes/`):** `ui_routes.register_routes` подключает `ui_status_push_routes`, `ui_birdfood_routes`, `ui_video_routes`, `ui_overview_timeline_routes` (сборка таймлайна — `ui_timeline_helpers`), `ui_corrections_dataset_routes`, `ui_species_catalog_routes`, `ui_settings_routes`, `ui_species_media_routes`; общие константы — `ui_route_constants`. `/api/ui/system/*`, метрики, visitors, diagnostics, bulk delete review-queue и species-registry — `ui_system_routes`, `ui_system_metrics_routes`, `ui_system_diagnostics_routes`, `ui_system_review_queue_routes`, `ui_system_species_registry_routes`. Ingest от процессора — `processor_routes`.

## База данных

- **SQLite** — `data/db/birdlense.db` (каталог задаётся через `DATA_DIR`; см. [CONFIGURATION.ru](./CONFIGURATION.ru.md)).
- **ORM:** Flask-SQLAlchemy; **эволюция схемы:** **Flask-Migrate / Alembic** — ревизии в `app/web/migrations/`. При старте `create_app()` через **`app_startup.apply_schema_migrations_and_seed`** выполняет `db.create_all()`, затем `upgrade()` — единый путь для новой установки и обновления (вместо разрозненных `ALTER TABLE` в коде приложения для отслеживаемых колонок).
- **Политика DDL (аудит, [#287](https://github.com/Gfermoto/BirdLense-Hub/issues/287)):** изменения таблиц/колонок — только новые ревизии Alembic в `migrations/versions/`, не в роутах и не в «ручном» старте. **PRAGMA** SQLite при подключении (I/O; не схема) регистрируются в **`flask_extensions.register_sqlite_connect_pragmas()`** из `create_app()`. Прочие `session.execute` в коде приложения — DML (например `DELETE`), не DDL.
- **Модели:** Video, Species, VideoSpecies, SpeciesVisit, BirdFood, ActivityLog и связанные таблицы (`app/web/models`).

## Внешние зависимости

| Сервис | Назначение |
|--------|------------|
| **Go2RTC** | Видеопотоки с IP-камер |
| **MQTT** | Frigate events, BirdNET sightings, Tasmota relay/sensor |
| **Telegram** | Push-уведомления (опционально) |
| **OpenWeather / Home Assistant** | Погода |

## Страницы UI

| Путь | Описание |
|------|----------|
| `/` | Overview — статистика, графики, виджет «Последняя птица», PDF-отчёт |
| `/timeline` | Timeline — записи (дата + время суток: Утро, День, Вечер, Ночь), экспорт CSV/JSON/eBird, iNaturalist |
| `/unknowns` | Legacy URL — редирект на `/timeline?review=1` |
| `/videos/:id` | VideoDetails — плеер (0.5x, 2x), детекции, спектрограмма, iNaturalist |
| `/live` | Live — поток с камер |
| `/species` | Сетка сезонности (визиты × вид × месяц); в навигации — пункт **Виды** |
| `/migration-calendar` | Тот же экран, что и `/species` (алиас / закладка) |
| `/species-directory` | Каталог видов карточками (расширенный справочник) |
| `/species/:id` | Species Summary — Xeno-canto (песни птиц) |
| `/library` | Календарь записей, экспорт датасета, прогон с диска при `video.source: file` |
| `/settings` | Настройки |
| `/system` | System — Storage, Activity, Monitor, Processor Logs |
| `/food` | Food Management |

## Индикаторы Overview

| Индикатор | Как проверяется |
|-----------|-----------------|
| **Video** | `check_video_reachable()` — HTTP GET snapshot первой камеры через go2rtc |
| **MQTT** | `check_mqtt_connected()` — подключение к брокеру (feed_service) |
| **ESPHome** | `check_esphome_reachable()` — HTTP к URL устройства |
| **YOLO** | Процессор шлёт в heartbeat `last_yolo_ok_at`; ok если в пределах 5 мин |
| **Processor** | Последний heartbeat в ActivityLog (каждые 60 сек) |

При `motion.source=frigate` показывается `mqtt` (триггер идёт через MQTT).

---

## Базовая линия maintainability (перед фичами)

Структурная отметка перед приоритетом продуктовых задач (волна Roadmap, апр. 2026):

- **Web ([#292](https://github.com/Gfermoto/BirdLense-Hub/issues/292)):** расширения Flask, старт приложения и тонкая фабрика `create_app` (`app/web/flask_extensions.py`, `app/web/app_startup.py`, `app/web/app.py`).
- **Processor ([#295](https://github.com/Gfermoto/BirdLense-Hub/issues/295)):** сборка стека детекции в `processor_bootstrap.py` / `detection_stack.py`; в рантайме — `DetectionStrategy` (ABC) с `detect` / `reset`. Для типизации и тестов без YOLO — **`DetectionStrategyProtocol`** в `app/processor/src/interfaces.py`; `FrameProcessor` зависит от протокола. Тест-заглушка: `app/processor/tests/test_detection_strategy_protocol.py`.
- **UI ([#296](https://github.com/Gfermoto/BirdLense-Hub/issues/296)):** **TanStack Query** на ключевых экранах; общие ключи кэша и HTTP — `app/ui/src/api/queryKeys.ts`, фетчеры в `api.tsx`. Запросы «ворот» настроек используют те же `queryKeys.settings.*`. Остальное (ещё экраны, контекст) — в issue.

---

См. также: [CONFIGURATION](./CONFIGURATION.ru.md), [API](./API.ru.md), [GLOSSARY](./GLOSSARY.ru.md).
