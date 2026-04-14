# Glossary — BirdLense Hub

Short definitions of terms used across [CONFIGURATION](./CONFIGURATION.md), [API](./API.md), and [ARCHITECTURE](./ARCHITECTURE.md).

[Русский](./GLOSSARY.ru.md)

---

## Core product

| Term | Meaning |
|------|---------|
| **Hub** | BirdLense Hub — this app: Docker stack with web UI, API, processor, optional MCP. |
| **Processor** | Background service inside the container: reads camera streams (via Go2RTC), runs detection/tracking, writes recordings, talks to MQTT, calls web API (`/api/processor/*`). |
| **Web / API** | Flask app behind nginx: `/api/ui/*` for the SPA, system routes, processor ingress. |

---

## Video & streams

| Term | Meaning |
|------|---------|
| **Go2RTC** | External (or sidecar) stream gateway. Hub pulls RTSP/WebRTC/HLS; nginx can proxy `/go2rtc/*`. Config: `video.go2rtc_url`. |
| **Live** | Browser view of streams — via Go2RTC UI proxy or processor MJPEG at `/processor/live`. |
| **Recording** | Clip under `data/recordings/YYYY/MM/DD/HHMMSS/video.mp4` plus DB row and detections. |

---

## Detection & ML

| Term | Meaning |
|------|---------|
| **YOLO** | On-device object model: binary bird/squirrel plus species classifier (EU ~491 species by default). |
| **ByteTrack** | Multi-object tracker across frames before a recording is finalized. |
| **NCNN** | Optional accelerated inference format on **x86/amd64**; paths under `processor` when `single_stage` / exported weights used. Not an ARM product target. |
| **Merge (detection)** | Combining YOLO, Frigate `sub_label`, and BirdNET MQTT inside a time window → one stored result per species (see `detection.*` keys). |
| **Unknowns** | Detections below `unknown_confidence_threshold`; listed for manual review. |

---

## Integrations

| Term | Meaning |
|------|---------|
| **Frigate** | NVR with object detection; Hub can subscribe to MQTT events and use **Bird Classification** `sub_label` as a species hint. |
| **BirdNET** | Audio bird ID — typically BirdNET-Go or BirdNET-Pi over MQTT; the Hub has no “pick your build” switch, only the JSON topic. Merge is not tied to the MQTT display language when a scientific name is present or aliases exist in the catalog. |
| **MQTT** | Single broker connection for Frigate topics, BirdNET, feeder relay, optional HA discovery. |
| **Home Assistant (HA)** | Smarthome platform; Hub can publish discovery topics and read weather entities. |

---

## Motion & triggers

| Term | Meaning |
|------|---------|
| **Motion source** | What starts a recording segment: OpenCV on stream, Frigate MQTT events, plain MQTT binary sensor, or ESPHome. Config: `motion.source`. |
| **Trigger** | Event that begins or extends recording; processor runs YOLO after a valid trigger (depending on mode). |

---

## Access & automation

| Term | Meaning |
|------|---------|
| **Admin (role)** | Unlocked with `settings_password` — full UI + feeder + system + restart processor. |
| **Contributor (role)** | Unlocked with `contributor_password` — labeling and exports without admin powers. |
| **Viewer** | Not unlocked — read-only browsing (exact export routes may still vary; see [ACCESS_CONTROL](./ACCESS_CONTROL.md)). |
| **MCP** | **Model Context Protocol** — optional `/mcp` endpoint for **authorized clients** (automation, integrations) to invoke hub tools; secured with `MCP_TOKEN` / `mcp.token`. See [MCP_SETUP](./MCP_SETUP.md). |
| **`PROCESSOR_SECRET`** | Shared secret for processor → web API (`X-Processor-Token`). |

---

## Data & exports

| Term | Meaning |
|------|---------|
| **Timeline** | Visits and clips aggregated by time; supports CSV/JSON/eBird export. |
| **Species visit** | Logical visit derived from detections and dedup windows (`dedup_window_seconds`). |
| **Dataset export** | ZIP of training crops for fine-tuning (see [DATASETS](./DATASETS.md)). |

---

## See also

[OVERVIEW](./OVERVIEW.md) · [SCENARIOS](./SCENARIOS.md) · [TROUBLESHOOTING](./TROUBLESHOOTING.md)
