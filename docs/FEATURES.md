# BirdLense Hub — Features

Capability overview. Per-version notes: [Changelog](./project/changelog.md).

[Русский](./FEATURES.ru.md)

---

## Core (always on)

| Feature | Description |
|---------|-------------|
| **Live video** | Go2RTC integration, MJPEG overlay with detections |
| **YOLO + ByteTrack** | Two-stage path: binary detector + species classifier |
| **EU model default** | ~491 species (birds-525 + iNaturalist). US (NABirds) weights available |
| **Motion triggers** | OpenCV, Frigate, MQTT, ESPHome |
| **BirdNET** | Merge audio sightings via MQTT |
| **Frigate** | Bird Classification `sub_label` merged with video ML |
| **Timeline** | Visits by date, playback, spectrograms |
| **Overview** | Stats, activity charts |
| **Species** | Species tree and per-species summary |
| **Weather** | OpenWeather or Home Assistant |
| **Telegram** | Detection alerts, optional best-frame photo |
| **Feeder** | Relay via MQTT (Tasmota) or ESPHome on detection |
| **MCP** | Model Context Protocol for external tools |

---

## Export & analytics

| Feature | API / UI | Since |
|---------|----------|-------|
| **CSV / JSON** | `GET /api/ui/timeline/export?format=csv|json` | 0.1.2 |
| **eBird** | `GET /api/ui/timeline/export?format=ebird` | 0.1.4 |
| **Region comparison** | `GET /api/ui/region-comparison` — your species vs regional eBird top list (Overview) | 0.1.9 |
| **PDF report** | `GET /api/ui/report/pdf?month=YYYY-MM` | 0.1.3 |
| **Prometheus** | `GET /metrics`, `GET /api/metrics` | 0.1.3 |
| **iNaturalist** | `GET /api/ui/detections/:id/crop` | 0.1.4 |
| **Dataset export** | `GET /api/ui/dataset/export` — ZIP train/val + `dataset_info.json` | 0.1.5 |

---

## UI highlights

| Feature | Description |
|---------|-------------|
| **Timeline: time of day** | Date picker + Morning / Day / Evening / Night (22–06) |
| **Unknowns** | `/unknowns` — low-confidence detections; manual correction |
| **Playback speed** | 0.5×, 2× in player |
| **Last bird widget** | Overview |
| **PWA** | Install prompt, offline cache |
| **Detection source** | YOLO / Frigate / BirdNET badges on cards |
| **Migration calendar** | `/migration-calendar` — visits by species × month |
| **Xeno-canto** | Calls on species page |
| **Per-species thresholds** | `processor.species_confidence_overrides` |
| **Training crops** | `processor.save_dataset_crops`; ZIP + relabel from System |
| **Download video** | Video details — Admin/Contributor after password |
| **Video prev/next** | Same UTC calendar day: arrows + counter on video details; `GET /api/ui/videos/:id/neighbors` |

---

## Integrations

| Feature | Config | Description |
|---------|--------|-------------|
| **Webhook** | `webhook.url` | POST JSON on each detection (IFTTT, Zapier, custom) |
| **eBird** | `ebird.country`, `ebird.state`, `ebird.location_name` | Checklist export |
| **Home Assistant** | `mqtt.ha_discovery`, `mqtt.broker` | MQTT discovery — Last Species, Bird at Feeder, … |
| **Grafana** | Prometheus scrape | Dashboards from Hub metrics |

---

## Notable config keys

| Section | Keys |
|---------|------|
| `processor` | `species_confidence_overrides`, `min_confidence_to_process` |
| `ui` | `unknown_confidence_threshold` |
| `webhook` | `url` |
| `ebird` | `country`, `state`, `location_name` |
| `secrets` | `xeno_canto_api_key`, `ebird_api_key` |

Full reference: [CONFIGURATION](./CONFIGURATION.md).

---

## Representative API routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/ui/health` | Health |
| GET | `/api/ui/timeline` | Visits in range |
| GET | `/api/ui/timeline/export` | CSV, JSON, eBird |
| GET | `/api/ui/unknowns` | Low confidence (`start_time`, `end_time`, `limit`) |
| GET | `/api/ui/region-comparison` | Region vs your list (needs `secrets.ebird_api_key`) |
| PATCH | `/api/ui/detections/:id` | Correct species |
| GET | `/api/ui/detections/:id/crop` | Crop for iNaturalist |
| GET | `/api/ui/videos/:id/download` | Download clip (role-gated) |
| GET | `/api/ui/videos/:id/neighbors` | Previous/next video IDs for the same UTC day as `start_time` |
| GET | `/api/ui/dataset/export` | Dataset ZIP |
| GET | `/api/ui/migration-calendar` | Migration calendar data |
| GET | `/api/ui/report/pdf` | PDF report |
| GET | `/api/ui/species/:id/xeno-canto` | Xeno-canto proxy |
| GET | `/metrics` | Prometheus |

Full spec: [OpenAPI (YAML)](./project/openapi.md) · narrative: [API](./API.md).

---

## See also

[API](./API.md) · [CONFIGURATION](./CONFIGURATION.md) · [GLOSSARY](./GLOSSARY.md) · [ROADMAP](./ROADMAP.md) · [OVERVIEW](./OVERVIEW.md)
