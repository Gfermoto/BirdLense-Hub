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

## Restarts, hangs, exit codes

One container runs nginx, gunicorn, and the processor loop. The processor can restart **inside** the container; the container exits if nginx/gunicorn/entrypoint die.

```bash
docker inspect birdlense --format '{{.State.ExitCode}} {{.State.Error}}'
docker logs birdlense --tail 200 2>&1
```

| Signal | Meaning |
|--------|---------|
| `137` | OOM kill |
| `139` | Segfault |
| `[h264] error while decoding MB` | Unstable RTSP / network |

**Mitigations:** set `mem_limit` in compose, log to file, watch Prometheus/Grafana.

---

## Processor thresholds: saved in UI, behavior unchanged

**Cause:** the web stack (gunicorn/Flask) and the **processor** are separate processes. Saving settings writes `user_config.yaml` and refreshes the in-memory config for the web app; the **recording/detection loop** does not re-read the file every frame, so it keeps the values from processor startup.

**Fix:** after changing `processor.*`, `detection.*`, or related keys, **restart the processor** (Settings UI button, `POST /api/ui/restart-processor`, or restart the `birdlense` container). To reduce Telegram noise without tightening DB acceptance, tune **`processor.min_confidence_to_notify`** — see [CONFIGURATION.md](./CONFIGURATION.md) → Processor.

---

## Slow web UI / API responses

**Common cause:** one container runs the **processor** (decode, detection, recording) and **gunicorn** (API). Under load the CPU is busy with frames and models, so UI requests wait in the gthread queue.

**What to try:**

1. **Docker resources** — default in `app/docker-compose.yml` is **4 CPUs / 4G RAM**. Raise `cpus` and `mem_limit` via `docker-compose.override.yml` (see `docker-compose.intel.example.yml` as an override pattern).
2. **API cache** — **Settings → Performance**: enable Redis (`performance.cache_redis_enabled`), confirm `REDIS_URL` in `.env` (compose default: `redis://redis:6379/0`). Without Redis, cache is in-process only.
3. **Concurrent requests** — single gunicorn worker with `gthread` (default **16** threads). Increase further: set `GUNICORN_THREADS=24` (or higher if the host allows) in `.env`, then `make restart`.
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
| 1 | `motion.source` still `opencv` | `user_config.yaml` → `motion.source` must be `frigate` (or appropriate MQTT path) |
| 2 | Frigate camera not in `video.cameras` | `id` must match Frigate camera name |
| 3 | `frigate_label_filter` empty | Default `["bird","Bird"]`; empty list drops all events |
| 4 | MQTT unavailable for a long time (broker/network) | Logs `MQTT aggregator disconnected` / `MQTT aggregator connected`; reconnect uses backoff (`mqtt.reconnect_min_delay` → `mqtt.reconnect_max_delay`) |
| 5 | Topic mismatch | Frigate `mqtt.topic_prefix` → events on `PREFIX/events` |
| 6 | QoS 0 + bad network | Events can be lost on reconnect |

**Order:** motion source → camera ids → logs (`Frigate trigger` / `Frigate event skipped`) → `GET /api/ui/status` (`mqtt: ok`).

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
