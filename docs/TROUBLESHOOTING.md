# Troubleshooting BirdLense Hub

[Русский](./TROUBLESHOOTING.ru.md)

---

## Video: Intel GPU recording falls back to CPU

**Settings → Video → Recording encode** can target CPU or Intel GPU. If logs show `Starting FFmpeg recording ... (CPU)` while Intel is selected, the container cannot access `/dev/dri/renderD128`.

**Fix:** install the Intel override and restart:

```bash
cp app/docker-compose.intel.example.yml app/docker-compose.override.yml
make stop && make start
```

Re-select **Intel GPU** in settings. **System** should show **Intel GPU (VA-API)** as active.

---

## Telegram: “App is UP!” spam loop

**Cause (historical):** entrypoint waited 30s for the API while `create_app()` blocked on Telegram startup (long timeouts). Health checks failed → container restart loop.

**Mitigations in tree:** longer wait, Telegram timeouts, startup marker under `/tmp/.birdlense_startup_notify_sent` to avoid duplicate sends.

**Diagnose:** `docker inspect birdlense --format '{{.RestartCount}}'` (increasing = loop). Logs: `create_app() invoked`, `notify_app_startup: sending` / `skip`.

Notification tuning: [CONFIGURATION](./CONFIGURATION.md) → Notifications.

---

## Single-container startup (entrypoint): if stuck {#single-container-startup-stuck}

The container runs **`app/scripts/entrypoint.sh`**: nginx → gunicorn → wait for **`GET /api/ui/health`** (up to ~400s) → optional MCP → **processor** loop (`processor/src/main.py`). See [ARCHITECTURE](./ARCHITECTURE.md#runtime-processes-ports-and-health-signals) and [RUNTIME_COUPLING](./RUNTIME_COUPLING.md).

| Symptom | Where to look |
| -------- | ---------------- |
| Blank page / 502 from nginx | `docker exec birdlense tail -100 /var/log/nginx/error.log` — upstream to `127.0.0.1:8000` failing |
| Health wait / slow first response | `docker logs birdlense` — `create_app()`, Telegram `notify_app_startup`, DB migrations; compare with [Telegram spam](#telegram-app-is-up-spam-loop) |
| UI loads but no detections / live | Processor is separate: logs for `main.py`, Go2RTC/MQTT; [processor thresholds](#processor-thresholds-saved-in-ui-behavior-unchanged) |
| Redis-related errors | `docker compose ps` — `birdlense-redis` healthy; `REDIS_URL` in `app/.env` |

Quick probes (from host, default port):

```bash
curl -sf "http://127.0.0.1:${BIRDLENSE_PORT:-8085}/api/ui/health"
curl -sf "http://127.0.0.1:${BIRDLENSE_PORT:-8085}/api/ui/readiness" | head -c 400
```

Inside the container, gunicorn listens on **`127.0.0.1:8000`** (not published); nginx on **`8080`**.

---

## Restarts, hangs, exit codes

One container runs nginx, gunicorn, and the processor loop. The processor can restart **inside** the container. nginx and gunicorn run in the background; if they die, the container may stay up but become unhealthy or partially broken. The container exits when the foreground entrypoint / processor loop exits or the runtime stops it.

```bash
docker inspect birdlense --format '{{.State.ExitCode}} {{.State.Error}}'
docker logs birdlense --tail 200 2>&1
```

| Signal | Meaning |
|--------|---------|
| `137` | OOM kill |
| `139` | Segfault |
| `[h264] error while decoding MB` | Unstable RTSP / network |

**nginx** (reverse proxy to gunicorn): **`/var/log/nginx/error.log`** and **`access.log`** inside the container (owned by **`birdlense`**). Example: `docker exec birdlense tail -100 /var/log/nginx/error.log`

**Mitigations:** set `mem_limit` in compose, log to file, watch Prometheus/Grafana.

---

## Processor thresholds: saved in UI, behavior unchanged

**Cause:** the web stack (gunicorn/Flask) and the **processor** are separate processes. Saving settings writes `user_config.yaml` and refreshes the in-memory config for the web app; the **recording/detection loop** does not re-read the file every frame, so it keeps the values from processor startup.

**Fix:** after changing `processor.*`, `detection.*`, or related keys, **restart the processor** (Settings UI button, `POST /api/ui/restart-processor`, or restart the `birdlense` container). To reduce Telegram noise without tightening DB acceptance, tune **`processor.min_confidence_to_notify`** — see [CONFIGURATION.md](./CONFIGURATION.md) → Processor.

---

## Detector weight contract: scope vs model class names {#detector-weight-contract-mismatch}

**Symptom (logs):** `Detector weight contract: ... miss scoped labels` — `processor.detector_scope` lists a label the current binary weights do not provide (e.g. only `Bird` in the model while scope includes `Rodent`).

**Not a crash** when `processor.detector_weight_contract` is `warn` (default). In `enforce` mode startup fails until weights and scope align.

**What to do:** (1) Set `processor.detector_scope` to match `model.names` / your training manifest. (2) Or deploy weights that include every scoped label, then restart the processor. (3) Do not put `Background` in scope — see [CV_ML_PREP.md](./CV_ML_PREP.md).

**Related:** [CV_ML_ROADMAP_PHASES.md](./CV_ML_ROADMAP_PHASES.md) (#368).

---

## Recording: session summary JSON in logs {#recording-session-summary-json}

**Diagnose weak detections / empty DB rows:** after each clip finalize, processor logs one structured line:

`recording_session_summary {…}` (JSON) — `frames_seen`, `yolo_frames_ran`, `low_light_blocked_frames`, `bytetrack_rows`, `post_fusion_persisted`, `mqtt_events_in_window`, `video_file_ok`, `runtime_profile`.

**Example:** `docker logs birdlense 2>&1 | grep recording_session_summary | tail`

---

## Processor: slow frame warnings at high resolution {#processor-slow-frame-warnings}

**Symptom:** many lines `Slow frame processing: …ms >= …ms`; low FPS in summaries — common at **2.7K+** with heavy YOLO.

**Note:** `processor.frame_processing_warn_ms` (default **450**) only reduces **log noise**; it does not speed up inference. For **latency**, tune `processor.binary_imgsz`, profiles, or resources — see [PROCESSOR_PERFORMANCE.md](./PROCESSOR_PERFORMANCE.md) and [RUNBOOKS.md](./RUNBOOKS.md). The System config-audit hint (`configAuditRuntimeSlowFrames`) explains the same trade-off.

---

## Slow web UI / API responses

**Common cause:** one container runs the **processor** (decode, detection, recording) and **gunicorn** (API). Under load the CPU is busy with frames and models, so UI requests wait in the gthread queue.

**What to try:**

1. **Docker resources** — default in `app/docker-compose.yml` is **4 CPUs / 4G RAM**. Raise `cpus` and `mem_limit` via `docker-compose.override.yml` (see `docker-compose.intel.example.yml` as an override pattern).
2. **API cache** — **Settings → Performance**: enable Redis (`performance.cache_redis_enabled`), confirm `REDIS_URL` in `.env` (compose default: `redis://redis:6379/0`). Without Redis, cache is in-process only.
3. **Concurrent requests** — single gunicorn worker with `gthread` (default **16** threads). Increase further: set `GUNICORN_THREADS=24` (or higher if the host allows) in `app/.env`, then restart the app container: `cd app && docker compose restart birdlense` (or `make stop && make start`).
4. **Disk / DB** — a very large `birdlense.db` or slow storage increases latency; **System** shows load. If needed, back up (**System → Storage**), stop the hub, then maintain SQLite (e.g. `sqlite3 birdlense.db "VACUUM;"`).
5. **Network** — Wi‑Fi or remote access adds latency unrelated to server CPU.

**Quick check:** `docker stats birdlense` — if CPU stays near the cgroup limit, expect slower UI; reduce load (resolution/FPS, external Frigate) or raise limits.

---

## Frigate / BirdNET: missed events

Pipeline: **Camera → go2rtc → Frigate → MQTT → BirdLense**. Debug from BirdLense upward.

Typical upstream noise: `non monotonically increasing dts`, timeouts, `404`, `No route to host` — unstable stream means no reliable detections.

**Quick checks:**

```bash
mosquitto_sub -t 'frigate/#' -v
curl -s http://YOUR_GO2RTC_HOST:1984/api/streams
```

**Fallback:** If Frigate is flaky, use **OpenCV** or **ESPHome** as an alternate motion source (**Settings → Motion**).

### Checklist: Frigate sees a bird, BirdLense does not record

| # | Cause | What to verify |
|---|--------|----------------|
| 1 | Frigate-триггер выключен | `user_config.yaml` → включите **`triggers.frigate.enabled: true`** и настройте **`mqtt.broker`** (и при необходимости OpenCV-параллель **`triggers.opencv.enabled`**) |
| 2 | Frigate camera not in `video.cameras` | `id` must match Frigate camera name |
| 3 | `frigate_label_filter` empty | Default `["bird","Bird"]`; empty list drops all events |
| 4 | MQTT unavailable for a long time (broker/network) | Logs `MQTT aggregator disconnected` / `MQTT aggregator connected`; reconnect uses backoff (`mqtt.reconnect_min_delay` → `mqtt.reconnect_max_delay`) |
| 5 | Topic mismatch | Frigate `mqtt.topic_prefix` → events on `PREFIX/events` |
| 6 | QoS 0 + bad network | Events can be lost on reconnect |

**Order:** motion source → camera ids → logs (`Frigate trigger` / `Frigate event skipped`) → `GET /api/ui/status` (`mqtt: ok`).

### BirdNET: FIFO fills but video merge / audio evidence does not match

Symptom: **System → Automation → BirdNET FIFO** shows events, but fusion with YOLO never shows `support` or BirdNET auto-thresholds do not apply.

| # | Cause | What to do |
|---|--------|------------|
| 1 | MQTT payload has **no scientific name** (`ScientificName` or equivalent), only a localized label | Prefer **BirdNET-Go** (usually sends Latin name). Otherwise add a **species alias** in the Hub registry for that MQTT string → taxon, or a `detection.species_mapping` entry. |
| 2 | Taxon **scientific name** in Hub does not match the MQTT value | Check `species_taxon.scientific_name` for typos/extra spaces. |
| 3 | Hub on **PostgreSQL** without a shared `birdlense.db` for the processor | SQLite-catalog auto-match is unavailable — use **`detection.species_mapping`** for MQTT strings. |
| 4 | Resolved name still differs from **video classifier** output | After catalog resolution, the merge key must match `normalize()` on video detections (see [CONFIGURATION.md](./CONFIGURATION.md) § MQTT). |

**On-server checks:** `GET /api/ui/health` — `mqtt: ok`; processor logs — `MQTT aggregator connected`; for verbose BirdNET path set `processor.birdnet_mqtt_observability_level: debug`. FIFO UI: **System → Automation → BirdNET FIFO snapshot** (admin password required).

---

## SQLite restore failed

Feature location: **System → Storage → Restore from file**.

- Only valid SQLite files are accepted (`.db/.sqlite`).
- Restore replaces the current DB, but creates an automatic `*.pre_restore_*.bak` next to `birdlense.db` first.
- `Invalid SQLite database file` means the upload is corrupt or not an SQLite DB.

Validate backup file before upload:

```bash
sqlite3 "/path/to/backup.db" "PRAGMA integrity_check;"
```

Expected output: `ok`.

---

## Live view: 502 or black screen

**502** — UI cannot reach go2rtc from inside the container.

| Network mode | Typical go2rtc URL |
|--------------|-------------------|
| `network_mode: host` | `http://localhost:1984` |
| bridge | `http://172.17.0.1:1984` or `http://YOUR_HOST_LAN_IP:1984` |

go2rtc must listen on `0.0.0.0:1984`. Test from host/container: `curl -s -o /dev/null -w "%{http_code}" http://...:1984/api/streams` → `200`.

**Workaround:** On **Live**, use **MJPEG** — stream is proxied through the processor.

---

## See also

[INSTALL](./INSTALL.md) · [CONFIGURATION](./CONFIGURATION.md) · [SCENARIOS](./SCENARIOS.md) · [GLOSSARY](./GLOSSARY.md)
