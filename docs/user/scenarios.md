# BirdLense Hub — Typical scenarios

[Русский](../ru/scenarios.ru.md)

---

## Scenario 1: Minimal setup (video only)

**Goal:** Bird detection from one camera, no MQTT or notifications.

1. Install Go2RTC (standalone or inside Frigate).
2. Add cameras in go2rtc `streams` (names must match BirdLense `stream_name`). For **H264 RTSP**, add **`ffmpeg:STREAM#video=mjpeg`** on each stream if you need **Live → MJPEG** — see [Configuration → Go2RTC streams and MJPEG](./configuration.md#go2rtc-streams-and-mjpeg-live-view) and [`docs/examples/go2rtc-streams.example.yaml`](../examples/go2rtc-streams.example.yaml).
3. Start BirdLense: `make pull` in `app/`.
4. Settings → Video: Go2RTC URL (`http://YOUR_GO2RTC_HOST:1984`).
5. Settings → Cameras: add stream name.
6. Trigger: OpenCV motion (default).

**Result:** Recordings on motion, YOLO classification (EU: birds-525 + iNaturalist, ~491 species).

---

## Scenario 2: European birds (Frigate + Bird Classification)

**Goal:** Accurate European species (jay, tit, etc.).

1. Frigate with [Bird Classification](https://docs.frigate.video/configuration/bird_classification/) enabled (`classification.bird.enabled: true`).
2. MQTT: Frigate publishes to `frigate/events` with `sub_label`.
3. BirdLense: Settings → MQTT — broker, Frigate topic. **Motion source: Frigate** (record on Frigate events).
4. Merge: YOLO + Frigate automatically. One result per species, max confidence.

**Result:** Eurasian Jay instead of Mourning Dove when Frigate classified the jay.

---

## Scenario 3: Audio (BirdNET over MQTT)

**Goal:** Voice-based recognition alongside video.

**Which BirdNET build:** there is **no** Hub toggle for “Pi vs Go”. Any stack that publishes **JSON** to your MQTT topic in a shape the processor understands will work — commonly **BirdNET-Go** or **BirdNET-Pi** (field names are listed in [CONFIGURATION.md](./configuration.md) § MQTT). Set broker and topic in Settings.

**Display locale (EN/RU, etc.):** you do **not** need to switch BirdNET’s UI language for video merge to work. The Hub maps each event to the **canonical species name** in your database using the **scientific name** from MQTT (BirdNET-Go usually includes it) and, when needed, **species aliases** in the registry. Details: same doc, § MQTT.

1. Your audio stack (e.g. BirdNET-Go or BirdNET-Pi) publishes recognitions to MQTT — often topic `birdnet` or a custom one (`mqtt.birdnet_topic`).
2. BirdLense: Settings → MQTT — broker, BirdNET topic.
3. Merge: YOLO + Frigate + BirdNET by time (`merge_window`).
4. **Spectrogram:** by default built after every clip (`processor.generate_spectrogram_always`); set **false** to build **only** when a BirdNET message falls in the recording window (less CPU). The player’s Audio tab shows it when the file exists.

**Result:** Audio-derived species add to or boost video detections; with a proper payload, merge does not depend on which language BirdNET uses for bird names.

---

## Scenario 4: Telegram notifications

**Goal:** Push when a bird is detected.

1. Create a bot (@BotFather → `/newbot`).
2. Get `chat_id` (e.g. via @RawDataBot).
3. Settings → Notifications: token, `chat_id`, `base_url` (Hub URL for links).
4. Enable `link_preview_large` for link previews (Bot API 9.4).

**Result:** Message like “Eurasian Jay Detected” with “Open Live” and page preview.

---

## Scenario 5: Feeder with relay (Tasmota / ESPHome)

**Goal:** Dispense food on detection.

1. Relay on Tasmota or ESPHome.
2. Settings → Feeder: source (mqtt/esphome), topic or URL, duration.
3. On detection BirdLense publishes to MQTT or calls ESPHome API.

**Result:** Feed dispenses when a bird appears.

---

## Scenario 6: Server deployment

See [INSTALL.md](./install.md) — “Deploy to server (`make deploy`)” and the operator checklist [DEPLOY_SERVER.md](./deploy-server.md): `scripts/deploy.local.sh`, **`DEPLOY_URL`** for post-deploy **`verify-stack`**, optional **`DEPLOY_SSH_PORT`**. After each deploy: `BASE_URL=... make verify` from the repo root. **x86_64 / amd64** (Intel or AMD) only; ARM / aarch64 not supported or planned.

---

## Scenario 7: Export to eBird

**Goal:** Upload species list to eBird.org for citizen science.

1. Timeline → pick date and time of day.
2. Export menu (download icon) → “Export for eBird”.
3. Settings → Advanced: country (US, RU, …), region, location name.
4. Import the downloaded CSV into eBird.org (Checklists → Import).

**Result:** Checklist in eBird Record format.

---

## Scenario 8: Export to iNaturalist

**Goal:** Send a detection frame to iNaturalist.

1. Timeline or video page → Share (Share to iNaturalist) on a detection.
2. Frame downloads; inaturalist.org/observations/upload opens.
3. Drop the file into the form; confirm or edit species.

**Result:** Observation on iNaturalist.

---

## Scenario 9: Manual review of “Unknowns”

**Goal:** Fix low-confidence detections.

1. Settings → Advanced: “Unknowns” threshold (default 0.5).
2. “Unknowns” page — list below threshold.
3. Pick correct species, Apply (settings password required).
4. Or open the video for visual check.

**Result:** Species corrected; stats updated.

---

## Scenario 10: PDF report and Grafana

**Goal:** Monthly summary and dashboards.

1. **PDF:** Overview → “PDF report” → pick month.
2. **Grafana:** Prometheus datasource, scrape `http://birdlense:8085/api/metrics` (or `http://YOUR_HOST:8085/api/metrics`). Metrics: CPU, memory, disk, GPU, detections, species, videos.

**Result:** Report and activity charts.

---

## Scenario 11: Research and model fine-tuning

See [TRAINING.md](../../archive/internal/docs-legacy/TRAINING.md), [DATASETS.md](../contributor/datasets.md) (**Canonical paths** for merge vs `brg/` vs zip names). Scripts: `scripts/datasets/`, merge → Colab.

---

## Troubleshooting

**Frigate saw a bird but BirdLense did not record:** see [TROUBLESHOOTING.md](./troubleshooting.md) — missed events, checklist.

---

See also: [OVERVIEW](./overview.md) · [INSTALL](./install.md) · [CONFIGURATION](./configuration.md) · [GLOSSARY](./glossary.md) · [ARCHITECTURE](../contributor/architecture.md).
