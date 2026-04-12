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
│  gunicorn:8000  →  Flask (/api/ui: ui_routes + domain ui_*;       │
│                      ui_system_*; processor_routes)               │
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
4. **Detector** — first-stage target confirmation (`Bird | Squirrel`).
5. **YOLO classifier** — species classification for detector-confirmed tracks.
6. **ByteTrack** — multi-object tracking and per-frame boxes.
7. **Fusion** — detector/classifier outcome + Frigate promotion + confidence boosters.
8. **Write** — `data/recordings/YYYY/MM/DD/HHMMSS/video.mp4`.
9. **Spectrogram** (when enabled / needed) — FFmpeg + librosa → e.g. `spectrogram_200.jpg`.
10. **API** — processor `POST /api/processor/videos` with fused detection payload.

### Frigate (optional)

1. Frigate publishes to MQTT (e.g. `frigate/events`).
2. **Bird Classification** in Frigate (`classification.bird.enabled: true`) adds `sub_label` (species).
3. Processor uses Frigate as a helper source in fusion: it may promote a generic detector fallback or boost confidence, but it does not create a persisted video detection on its own.

### BirdNET (optional)

1. BirdNET-Pi / BirdNET-Go publishes to MQTT (e.g. topic `birdnet`).
2. Processor **MQTTEventAggregator** consumes messages.
3. BirdNET adjusts classifier confidence thresholds and other confidence logic, but it does not create final video labels.

**Models:** EU classifier (~491 species) in `best.pt`; US (NABirds) backup `best_US.pt`. See [TRAINING](./TRAINING.md).

### Web UI

1. **React SPA** — static assets behind nginx.
2. **JSON API** — `/api/ui/*` (health, status, timeline, exports, settings, unknowns, …).
3. **Metrics** — `GET /metrics`, `GET /api/metrics` (Prometheus).
4. **Recorded media** — `/data/recordings/...` (nginx alias).
5. **Live** — `/processor/live` (MJPEG from processor) or Go2RTC proxied UI under `/go2rtc/`.

**Flask modules (`app/web/routes/`):** `ui_routes.register_routes` composes `ui_status_push_routes`, `ui_birdfood_routes`, `ui_video_routes`, `ui_overview_timeline_routes` (timeline merge helpers in `ui_timeline_helpers`), `ui_corrections_dataset_routes`, `ui_species_catalog_routes`, `ui_settings_routes`, `ui_species_media_routes`; shared literals in `ui_route_constants`. `/api/ui/system/*`, metrics, visitors, diagnostics, review-queue bulk delete, and species-registry use `ui_system_routes`, `ui_system_metrics_routes`, `ui_system_diagnostics_routes`, `ui_system_review_queue_routes`, and `ui_system_species_registry_routes`. Processor ingest: `processor_routes`.

---

## Database

- **SQLite** — `data/db/birdlense.db` (path configurable via `DATA_DIR`; see [CONFIGURATION](./CONFIGURATION.md)).
- **ORM:** Flask-SQLAlchemy; **schema evolution:** **Flask-Migrate / Alembic** — revision scripts under `app/web/migrations/`. On startup, `create_app()` calls **`app_startup.apply_schema_migrations_and_seed`**, which runs `db.create_all()` then `upgrade()` so new installs and upgrades share one path (replaces ad-hoc `ALTER TABLE` in application code for tracked columns).
- **DDL policy (audit, [#287](https://github.com/Gfermoto/BirdLense-Hub/issues/287)):** table/column changes belong in new Alembic revisions under `migrations/versions/`, not in route or startup code. SQLite **PRAGMA** tuning on connect (I/O performance; not schema) is registered via **`flask_extensions.register_sqlite_connect_pragmas()`** from `create_app()`. Other `session.execute` usages in app code are DML (e.g. deletes), not DDL.
- **Entities:** Video, Species, VideoSpecies, SpeciesVisit, BirdFood, ActivityLog, and related tables (see `app/web/models`).

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

## Maintainability baseline (pre-features gate)

This is the **structural** checkpoint before prioritizing product features (GitHub Roadmap wave, Apr 2026):

- **Web ([#292](https://github.com/Gfermoto/BirdLense-Hub/issues/292)):** Flask extensions, startup, and a thin `create_app` factory (`app/web/flask_extensions.py`, `app/web/app_startup.py`, `app/web/app.py`).
- **Processor ([#295](https://github.com/Gfermoto/BirdLense-Hub/issues/295)):** Detection stack is assembled in `processor_bootstrap.py` / `detection_stack.py`; runtime uses `DetectionStrategy` (ABC) with `detect` / `reset`. For typing and tests without loading YOLO, `app/processor/src/interfaces.py` defines **`DetectionStrategyProtocol`**; `FrameProcessor` depends on that protocol. See `app/processor/tests/test_detection_strategy_protocol.py`.
- **UI ([#296](https://github.com/Gfermoto/BirdLense-Hub/issues/296)):** **TanStack Query** on primary routes; stable cache keys and HTTP helpers live under `app/ui/src/api/` (`queryKeys.ts`, `api.tsx` fetchers). Settings gate queries use the same `queryKeys.settings.*` contract. Further consolidation (more screens, context) stays in the issue.

---

## See also

[CONFIGURATION](./CONFIGURATION.md) · [API](./API.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [GLOSSARY](./GLOSSARY.md) · [OVERVIEW](./OVERVIEW.md)
