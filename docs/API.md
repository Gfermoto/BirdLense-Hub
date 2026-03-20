# BirdLense Hub — HTTP API

**Version:** 0.2.2

Authoritative contract: [OpenAPI YAML](./project/openapi.md) (import into Redoc, Stoplight, or IDE).

**Interactive (browser):** [OpenAPI (Redoc)](reference/openapi.md).

[Русский](./API.ru.md)

---

## UI API (`/api/ui/*`)

All paths in this table are prefixed with `/api/ui` (e.g. `/health` → `GET /api/ui/health`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness |
| `/status` | GET | Component status: `web`, `processor`, `mqtt`, `esphome`, `yolo` — `ok` \| `error` \| `not_configured` \| `not_used` \| `unknown` |
| `/cameras` | GET | Camera list |
| `/weather` | GET | Weather snapshot |
| `/timeline` | GET | Visits in range (`start_time`, `end_time`) |
| `/timeline/export` | GET | CSV, JSON, or eBird (`format=csv|json|ebird`) |
| `/videos/:id` | GET | Video detail |
| `/overview` | GET | Overview dashboard payload |
| `/species` | GET | Species list |
| `/birdfood` | GET/POST | Food list / add |
| `/birdfood/:id/toggle` | PATCH | Toggle food entry |
| `/bird_families` | GET | Bird family list |
| `/feed/dispense` | POST | Trigger feeder (**Admin** session or MCP Bearer — see [ACCESS_CONTROL](./ACCESS_CONTROL.md)) |
| `/settings` | GET/PATCH | Read/update settings |
| `/settings/requires-password` | GET | Whether a password is configured |
| `/settings/verify-password` | POST | Unlock session (`password` → `role`: `admin` \| `contributor`) |
| `/settings/check-access` | GET | Admin gate (200/403) |
| `/unknowns` | GET | Low-confidence detections (`start_time`, `end_time`, `limit`) |
| `/region-comparison` | GET | Your species vs regional eBird (needs `secrets.ebird_api_key`) |
| `/detections/:id` | PATCH | Correct species (`species_id`) — Contributor+ |
| `/detections/:id/crop` | GET | JPEG crop for iNaturalist |
| `/dataset/export` | GET | Dataset ZIP — Contributor+ |
| `/push/vapid-public` | GET | Web Push VAPID public key |
| `/push/subscribe` | POST | Register push subscription |
| `/report/pdf` | GET | Monthly PDF (`month=YYYY-MM` or time range) |
| `/migration-calendar` | GET | Visits aggregated by species × month |
| `/species/:id/xeno-canto` | GET | Xeno-canto clips for species |
| `/species/:id/summary` | GET | Species summary |
| `/restart-processor` | POST | Restart processor (**Admin**) |

---

## Prometheus

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metrics` | GET | Prometheus text format |
| `/api/metrics` | GET | Same (Grafana-friendly path) |

Scrape config: [CONFIGURATION](./CONFIGURATION.md) → Prometheus / Grafana.

---

## System & storage (`/api/ui/...`)

| Path | Method | Description |
|------|--------|-------------|
| `/api/ui/system/metrics` | GET | CPU, RAM, disk, GPU, encoding |
| `/api/ui/system/activity` | GET | Activity by day |
| `/api/ui/storage/stats` | GET | Recording storage stats |
| `/api/ui/storage/purge` | POST | Purge by date (**Admin**) |
| `/api/ui/system/retention` | POST | Run retention policy |
| `/api/ui/system/regenerate-spectrograms` | POST | Regenerate spectrograms |
| `/api/ui/system/regenerate-spectrograms/status` | GET | Job status |
| `/api/ui/system/regenerate-tracks` | POST | Regenerate tracks |
| `/api/ui/system/regenerate-tracks/status` | GET | Job status |
| `/api/ui/system/recordings/scan` | POST | Scan & import recordings |
| `/api/ui/system/logs` | GET | Processor log tail (`?lines=100`) |

More maintenance endpoints exist — see `ui_system_routes.py` and OpenAPI.

---

## Processor API (`/api/processor/*`)

Internal contract between **processor** and **web**. When `PROCESSOR_SECRET` is set, send header **`X-Processor-Token: <secret>`**.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/videos` | POST | Upsert recording + detections |
| `/species/active` | PUT | Active species snapshot |
| `/notify/detections` | POST | Detection notification (e.g. Telegram pipeline) |
| `/notify/motion` | POST | Motion notification |
| `/activity_log` | POST | Heartbeat / processor status |

---

## Authentication summary

| Surface | Behavior |
|---------|----------|
| **Default** | No login; all UI routes open if no passwords configured |
| **Settings / feeder / system** | Optional `settings_password`; **Admin** unlock via `verify-password` |
| **Contributor** | Optional `contributor_password` — labeling & exports without full admin |
| **MCP** | Optional `MCP_TOKEN` — `Authorization: Bearer <token>` |
| **Processor** | Optional `PROCESSOR_SECRET` — `X-Processor-Token` |

Details: [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [CONFIGURATION](./CONFIGURATION.md).

---

## See also

[CONFIGURATION](./CONFIGURATION.md) · [ARCHITECTURE](./ARCHITECTURE.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [FEATURES](./FEATURES.md) · [GLOSSARY](./GLOSSARY.md)
