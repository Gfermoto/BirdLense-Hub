# BirdLense Hub — Architecture

High-level layout of the single-container app, data paths, and integrations. For feature lists see [FEATURES](./FEATURES.md); for HTTP details see [API](./API.md) and [OpenAPI (YAML)](./project/openapi.md).

[Русский](./ARCHITECTURE.ru.md)

---

## Single container (`birdlense`)

```
┌─────────────────────────────────────────────────────────────────┐
│  One container (birdlense)                                       │
├─────────────────────────────────────────────────────────────────┤
│  nginx:8080  ──►  /            →  static (React SPA)             │
│                 /api           →  Flask :8000                    │
│                 /mcp, /sse     →  MCP :8001 (if enabled)         │
│                 /processor/live →  processor :8082 (MJPEG)       │
│                 /go2rtc/*     →  upstream Go2RTC               │
│                 /data/*       →  /app/data (recordings, DB)      │
├─────────────────────────────────────────────────────────────────┤
│  gunicorn:8000  →  Flask (ui_routes, ui_system_routes,           │
│                      processor_routes)                           │
├─────────────────────────────────────────────────────────────────┤
│  MCP :8001 (optional)  →  FastMCP, tools from OpenAPI          │
├─────────────────────────────────────────────────────────────────┤
│  processor  →  main.py: Go2RTC ingest, YOLO, ByteTrack,          │
│                recording, FFmpeg spectrograms, MQTT              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data flows

### Video (default path)

1. **Go2RTC** (external) — RTSP / WebRTC / HLS into the hub.
2. **Processor** reads frames from Go2RTC.
3. **Motion** (OpenCV, Frigate MQTT, plain MQTT, or ESPHome) starts a recording segment.
4. **YOLO** — bird/squirrel detection and species classification.
5. **ByteTrack** — multi-object tracking.
6. **Write** — `data/recordings/YYYY/MM/DD/HHMMSS/video.mp4`.
7. **Spectrogram** (when BirdNET is in the merge window) — FFmpeg + librosa → e.g. `spectrogram_200.jpg`.
8. **API** — processor `POST /api/processor/videos` with detection payload.

### Frigate (optional)

1. Frigate publishes to MQTT (e.g. `frigate/events`).
2. **Bird Classification** in Frigate (`classification.bird.enabled: true`) adds `sub_label` (species).
3. Processor merges `sub_label` with YOLO output (see [CONFIGURATION](./CONFIGURATION.md) → Detection).

### BirdNET (optional)

1. BirdNET-Pi / BirdNET-Go publishes to MQTT (e.g. topic `birdnet`).
2. Processor **MQTTEventAggregator** consumes messages.
3. Detections merge with video results using `merge_window_seconds`.

**Models:** EU classifier (~491 species) in `best.pt`; US (NABirds) backup `best_US.pt`. See [TRAINING](./TRAINING.md).

### Web UI

1. **React SPA** — static assets behind nginx.
2. **JSON API** — `/api/ui/*` (health, status, timeline, exports, settings, unknowns, …).
3. **Metrics** — `GET /metrics`, `GET /api/metrics` (Prometheus).
4. **Recorded media** — `/data/recordings/...` (nginx alias).
5. **Live** — `/processor/live` (MJPEG from processor) or Go2RTC proxied UI under `/go2rtc/`.

---

## Database

- **SQLite** — `data/db/birdlense.db`
- **Entities:** Video, Species, VideoSpecies, SpeciesVisit, BirdFood, ActivityLog (see code under `app/web/models`).

---

## External services

| Service | Role |
|---------|------|
| **Go2RTC** | Camera streams |
| **MQTT** | Frigate, BirdNET, Tasmota, HA discovery |
| **Telegram** | Optional alerts |
| **OpenWeather / Home Assistant** | Weather widget |

---

## UI routes (SPA)

| Path | Purpose |
|------|---------|
| `/` | Overview — stats, charts, last bird, PDF report |
| `/timeline` | Visits, time-of-day filter, CSV/JSON/eBird export, iNaturalist |
| `/unknowns` | Low-confidence detections for manual review |
| `/videos/:id` | Player, detections, spectrogram, share |
| `/live` | Live streams |
| `/species` | Redirect to Migration Calendar (legacy compatibility route) |
| `/species/:id` | Species summary, Xeno-canto |
| `/settings` | Configuration |
| `/system` | Storage, activity, monitor, processor logs |
| `/food` | Food management |

---

## Overview status indicators

| Indicator | Mechanism |
|-----------|-----------|
| **Video** | HTTP snapshot to Go2RTC for first configured camera |
| **MQTT** | Broker connectivity (feed service path) |
| **ESPHome** | HTTP reachability of feeder device |
| **YOLO** | Processor heartbeat field `last_yolo_ok_at` (fresh within ~5 min) |
| **Processor** | Heartbeat rows in ActivityLog (~60 s) |

When `motion.source` is `frigate`, the **MQTT** tile reflects the Frigate/MQTT path.

---

## See also

[CONFIGURATION](./CONFIGURATION.md) · [API](./API.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [GLOSSARY](./GLOSSARY.md) · [OVERVIEW](./OVERVIEW.md)
