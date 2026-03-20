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
│  gunicorn:8000  →  Flask API (ui_routes, ui_system_routes,       │
│                     processor_routes)                            │
├─────────────────────────────────────────────────────────────────┤
│  MCP:8001 (опционально)  →  FastMCP, tools из OpenAPI            │
├─────────────────────────────────────────────────────────────────┤
│  processor  →  main.py: Go2RTC stream, YOLO, ByteTrack,          │
│                запись видео, FFmpeg спектрограммы, MQTT           │
└─────────────────────────────────────────────────────────────────┘
```

## Потоки данных

### Видео

1. **Go2RTC** (внешний) → RTSP/HLS поток
2. **Processor** подключается к Go2RTC, получает кадры
3. **Триггер** (OpenCV, Frigate, MQTT, ESPHome) → начало записи
4. **YOLO** — детекция птиц в кадре
5. **ByteTrack** — трекинг
6. **Запись** → `data/recordings/YYYY/MM/DD/HHMMSS/video.mp4`
7. **Спектрограмма** → FFmpeg (аудио) + librosa (mel) → `spectrogram_200.jpg`
8. **API** → processor отправляет POST `/api/processor/videos` с детекциями

### Видео: Frigate (опционально)

1. **Frigate** → публикует в MQTT `frigate/events` (детекция + Bird Classification)
2. **Bird Classification** — `classification.bird.enabled: true` в Frigate, добавляет `sub_label` с видом (INat)
3. **Processor** парсит `sub_label` и использует как species при слиянии

### Аудио (BirdNET)

1. **BirdNET-Pi/Go** (внешний) → публикует в MQTT топик `birdnet`
2. **Processor** (MQTTEventAggregator) подписан на топик
3. Слияние с детекциями YOLO по времени (merge_window)

**Европейские птицы:** EU-модель (YOLO11n-cls, ~491 вид) активна в `best.pt`. US (NABirds) — резерв в `best_US.pt`. Frigate + BirdNET — дополнение. Слияние: один результат на вид (max confidence).

### UI

1. **React SPA** → `index.html`, static assets
2. **API** → `/api/ui/*` (health, status, timeline, timeline/export, videos, unknowns, detections/:id/crop, report/pdf, species/:id/xeno-canto, settings, birdfood и др.)
3. **Метрики** → `GET /metrics`, `GET /api/metrics` (Prometheus)
4. **Видео** → `/data/recordings/...` (nginx alias)
5. **Live** → `/processor/live` (MJPEG от processor) или `/go2rtc/stream.html`

## База данных

- **SQLite** — `data/db/birdlense.db`
- **Модели:** Video, Species, VideoSpecies, SpeciesVisit, BirdFood, ActivityLog

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
| `/unknowns` | Неизвестные — детекции с низкой confidence для ручной проверки |
| `/videos/:id` | VideoDetails — плеер (0.5x, 2x), детекции, спектрограмма, iNaturalist |
| `/live` | Live — поток с камер |
| `/species` | Bird Directory — дерево видов |
| `/species/:id` | Species Summary — Xeno-canto (песни птиц) |
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

См. также: [CONFIGURATION](./CONFIGURATION.ru.md), [API](./API.ru.md), [GLOSSARY](./GLOSSARY.ru.md).
