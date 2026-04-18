# BirdLense Hub — HTTP API

**Version:** the release semver in repository root `VERSION` (mirrored in `app/web/openapi.yaml`).

Authoritative contract: [OpenAPI YAML](./project/openapi.md) (import into Redoc, Stoplight, or IDE).

**Interactive (browser):** [OpenAPI (Redoc)](reference/openapi.md).

[Русский](./API.ru.md)

---

## UI API (`/api/ui/*`)

All paths in this table are prefixed with `/api/ui` (e.g. `/health` → `GET /api/ui/health`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness |
| `/readiness` | GET | Hub readiness: DB, writable dirs, component checks — **200** when `"ready": true`, **503** with JSON body when not ready (load balancers / `verify-stack`) |
| `/status` | GET | Component status: `web`, `processor`, `mqtt`, `esphome`, `yolo` — `ok` \| `error` \| `not_configured` \| `not_used` \| `unknown` |
| `/cameras` | GET | Camera list |
| `/weather` | GET | Weather snapshot |
| `/timeline` | GET | Visits in range (`start_time`, `end_time`) |
| `/timeline/export` | GET | CSV, JSON, or eBird (`format=csv|json|ebird`) |
| `/videos/:id` | GET | Video detail |
| `/videos/:id/neighbors` | GET | Previous/next video IDs. Supports local day and cross-day fallback via `day_scope`, `tz_offset_minutes`, `cross_day`; response includes `day_scope`, `day_label`, `timezone_offset_minutes` |
| `/overview` | GET | Overview dashboard payload |
| `/species` | GET | Species list |
| `/birdfood` | GET/POST | Food list / add |
| `/birdfood/:id/toggle` | PATCH | Toggle food entry |
| `/bird_families` | GET | Bird family list |
| `/feed/dispense` | POST | Trigger feeder (**Admin** session or MCP Bearer — see [ACCESS_CONTROL](./ACCESS_CONTROL.md)) |
| `/settings` | GET/PATCH | Read/update settings |
| `/settings/requires-password` | GET | Whether a password is configured |
| `/settings/verify-password` | POST | Unlock session (`password` → `role`: `admin` \| `contributor`). **401** if wrong password; **429** + `Retry-After` after 5 failed attempts / 60s per IP — see [ACCESS_CONTROL](./ACCESS_CONTROL.md) |
| `/settings/check-access` | GET | Session unlock state: `{ unlocked, role? }` — always **200** (locked → `unlocked: false`; no red 403 in browser for probes) |
| `/unknowns` | GET | Low-confidence detections (`start_time`, `end_time`, `limit`) |
| `/region-comparison` | GET | Your species vs regional eBird (needs `secrets.ebird_api_key`) |
| `/detections/:id` | PATCH | Correct species (`species_id`) — Contributor+ |
| `/detections/:id/crop` | GET | JPEG crop for iNaturalist |
| `/dataset/export` | GET | Dataset ZIP — Contributor+ |
| `/push/vapid-public` | GET | Web Push VAPID public key |
| `/push/subscribe` | POST | Register push subscription |
| `/report/pdf` | GET | Monthly PDF (`month=YYYY-MM` or time range) |
| `/migration-calendar` | GET | Visits aggregated by species × month. Query: `catalog`=`active`\|`full`, `evidence`=`all`\|`video`, plus optional year/date filters |
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
| `/api/ui/system/metrics` | GET | Live snapshot: CPU, RAM, disk, GPU (`encoding` hints when GPU chart applies) |
| `/api/ui/system/metrics/history` | GET | Downsampled time series for System charts (`?hours=`, `?max_points=`) |
| `/api/ui/system/visitors` | GET | Unique visitor sessions over `?days=` (SpeciesVisit aggregate) |
| `/api/ui/system/activity` | GET | Activity by day |
| `/api/ui/storage/stats` | GET | Recording storage stats |
| `/api/ui/storage/purge` | POST | Purge recordings: JSON `{"date":"YYYY-MM-DD"}` (on or before that day) or `{"start_date","end_date"}` inclusive range (**Admin**) |
| `/api/ui/system/retention` | POST | Run retention policy |
| `/api/ui/system/regenerate-spectrograms` | POST | Regenerate spectrograms |
| `/api/ui/system/regenerate-spectrograms/status` | GET | Job status |
| `/api/ui/system/regenerate-tracks/status` | GET | Job status |
| `/api/ui/system/recordings/scan` | POST | Scan & import recordings |
| `/api/ui/system/logs` | GET | Processor log tail (`?lines=100`) |

### Species registry (`/api/ui/system/species-registry/*`)

**Admin** (unlocked settings session). Full request/response shapes: **`app/web/openapi.yaml`**.

| Path | Method | Description |
|------|--------|-------------|
| `/api/ui/system/species-registry/seed` | POST | Seed registry + aliases from bundled mapping |
| `/api/ui/system/species-registry/backfill` | POST | Link `Species` rows to taxa; JSON `dry_run` (default true), optional `limit` |
| `/api/ui/system/species-registry/unresolved` | GET | Top unresolved names (`?limit=`) |
| `/api/ui/system/species-registry/enrich-metadata/start` | POST | Start async metadata enrichment (`limit`, `retry_failed_only`) → **202** / **409** |
| `/api/ui/system/species-registry/enrich-metadata/status` | GET | Enrichment job status |
| `/api/ui/system/species-registry/health` | GET | Rollout / coverage health |
| `/api/ui/system/species-registry/materialize-allowlist` | POST | Create missing allowlist species (`dry_run`, `fill_metadata`, `limit`) |
| `/api/ui/system/species-registry/repair-cards/start` | POST | Start card image repair → **202** / **409** |
| `/api/ui/system/species-registry/repair-cards/status` | GET | Repair job status + coverage |
| `/api/ui/system/species-registry/data-quality` | GET | Catalog quality report (`?duplicate_limit=`) |
| `/api/ui/system/species-registry/classifier-dataset-alignment` | GET | Classifier vs DB vs dataset dirs (`?classifier_limit=` …) |
| `/api/ui/system/species-registry/coverage-metrics` | GET | Coverage segments |
| `/api/ui/system/species-registry/tuning-targets/export` | GET | Training targets; query `format=json` (default) or `format=csv` |

More maintenance endpoints exist — see `ui_system_*.py` and OpenAPI.

---

## Processor API (`/api/processor/*`)

Internal contract between **processor** and **web**. When `PROCESSOR_SECRET` is set, send header **`X-Processor-Token: <secret>`**.

In **`app/web/openapi.yaml`**, choose the **`…/api/processor`** server entry in your OpenAPI client; paths below are relative to that base (not under `/api/ui`).

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

## UI routing note (operator-facing)

- Legacy route **`/unknowns`** is kept for bookmarks and redirects to **`/timeline?review=1`**.
- Review mode uses the same unknown-detection API (`GET /api/ui/unknowns`), while normal Timeline mode uses `GET /api/ui/timeline`.

---

## See also

[CONFIGURATION](./CONFIGURATION.md) · [ARCHITECTURE](./ARCHITECTURE.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.md) · [FEATURES](./FEATURES.md) · [GLOSSARY](./GLOSSARY.md)
