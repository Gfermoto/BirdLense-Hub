# BirdLense Hub — Typical scenarios

[Русский](./SCENARIOS.ru.md)

---

## Scenario 1: Minimal setup (video only)

**Goal:** Bird detection from one camera, no MQTT or notifications.

1. Install Go2RTC (standalone or inside Frigate).
2. Add the camera in Go2RTC.
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

## Scenario 3: Audio (BirdNET-Pi / BirdNET-Go)

**Goal:** Voice-based recognition alongside video.

1. BirdNET-Pi or BirdNET-Go publishes to MQTT topic `birdnet`.
2. BirdLense: Settings → MQTT — broker, BirdNET topic.
3. Merge: YOLO + Frigate + BirdNET by time (`merge_window`).
4. **Spectrogram** is generated **only** when a BirdNET recognition message arrives in the recording window. Automatic in that case. Audio tab in the player shows the spectrogram.

**Result:** Audio-derived species add to or boost video detections.

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

See [INSTALL.md](./INSTALL.md) — “Server deployment (`make deploy`)”. x86/amd64 only; ARM not supported.

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

See [TRAINING.md](./TRAINING.md), [DATASETS.md](./DATASETS.md). Scripts: `scripts/datasets/`, merge → Colab.

---

## Troubleshooting

**Frigate saw a bird but BirdLense did not record:** see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) — missed events, checklist.

---

See also: [OVERVIEW](./OVERVIEW.md) · [INSTALL](./INSTALL.md) · [CONFIGURATION](./CONFIGURATION.md) · [GLOSSARY](./GLOSSARY.md) · [ARCHITECTURE](./ARCHITECTURE.md).
