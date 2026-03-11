# Архитектура BirdLense Hub

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
7. **Спектрограмма** → FFmpeg → `spectrogram_200.jpg`
8. **API** → processor отправляет POST `/api/processor/videos` с детекциями

### Аудио (BirdNET)

1. **BirdNET-Pi/Go** (внешний) → публикует в MQTT топик `birdnet`
2. **Processor** (MQTTEventAggregator) подписан на топик
3. Слияние с детекциями YOLO по времени (merge_window)

### UI

1. **React SPA** → `index.html`, static assets
2. **API** → `/api/ui/*` (health, status, timeline, videos, settings, birdfood и др.)
3. **Видео** → `/data/recordings/...` (nginx alias)
4. **Live** → `/processor/live` (MJPEG от processor) или `/go2rtc/stream.html`

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
| `/` | Overview — статистика, графики |
| `/timeline` | Timeline — записи по дням |
| `/videos/:id` | VideoDetails — плеер, детекции, спектрограмма |
| `/live` | Live — поток с камер |
| `/species` | Bird Directory — дерево видов |
| `/species/:id` | Species Summary |
| `/settings` | Настройки |
| `/system` | System — Storage, Activity, Monitor, Processor Logs |
| `/food` | Food Management |

---

См. также: [CONFIGURATION.md](./CONFIGURATION.md), [API.md](./API.md).
