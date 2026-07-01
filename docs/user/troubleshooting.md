# Устранение проблем

[Русский](../ru/troubleshooting.ru.md)

---

## Video: Intel GPU recording falls back to CPU

**Settings → Video → Recording encode** can target Jetson (NVENC) or CPU. If logs show `Recording ... (CPU)` while Jetson is selected, the container cannot access NVIDIA GPU.

**Fix:** verify NVIDIA runtime, `nvidia-smi` in container:

```bash
docker exec birdlense nvidia-smi
```

Re-select **Jetson** in settings. **System** should show GPU metrics. No Intel override needed on Orin.

---

## Telegram: “App is UP!” spam loop

**Cause (historical):** entrypoint waited 30s for the API while `create_app()` blocked on Telegram startup (long timeouts). Health checks failed → container restart loop.

**Mitigations in tree:** longer wait, Telegram timeouts, startup marker under `/tmp/.birdlense_startup_notify_sent` to avoid duplicate sends.

**Diagnose:** `docker inspect birdlense --format '{{.RestartCount}}'` (increasing = loop). Logs: `create_app() invoked`, `notify_app_startup: sending` / `skip`.

Notification tuning: [CONFIGURATION](./configuration.md) → Notifications.

---

## Single-container startup (entrypoint): if stuck {#single-container-startup-stuck}

The container runs **`app/scripts/entrypoint.sh`**: nginx → gunicorn → wait for **`GET /api/ui/health`** (up to ~400s) → optional MCP → **processor** loop (`processor/src/main.py`). See [ARCHITECTURE](../contributor/architecture.md#runtime-processes-ports-and-health-signals) and [RUNTIME_COUPLING](../archive/internal/docs-legacy/RUNTIME_COUPLING.md).

| Symptom | Where to look |
| -------- | ---------------- |
| Blank page / 502 from nginx | `docker exec birdlense tail -100 /var/log/nginx/error.log` — upstream to `127.0.0.1:8000` failing |
| Health wait / slow first response | `docker logs birdlense` — `create_app()`, Telegram `notify_app_startup`, DB migrations; compare with [Telegram spam](#telegram-app-is-up-spam-loop) |
| UI loads but no detections / live | Processor is separate: logs for `main.py`, Go2RTC/MQTT; [processor thresholds](#processor-thresholds-saved-in-ui-behavior-unchanged) |
| Redis-related errors | `docker compose ps` — `birdlense-redis` healthy; `REDIS_URL` in `app/.env` |

Quick probes (from host, default port):

```bash
diff app/.env.example app/.env
```

## 403 Forbidden на API

PROCESSOR_SECRET не совпадает:

```bash
# Проверить
grep PROCESSOR_SECRET app/.env
# Сгенерировать
python3 -c "import secrets; print(secrets.token_hex(16))"
# Обновить в .env и перезапустить
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

**Fix:** after changing `processor.*`, `detection.*`, or related keys, **restart the processor** (Settings UI button, `POST /api/ui/restart-processor`, or restart the `birdlense` container). To reduce Telegram noise without tightening DB acceptance, tune **`processor.min_confidence_to_notify`** — see [CONFIGURATION.md](./configuration.md) → Processor.

---

## Detector weight contract: scope vs model class names {#detector-weight-contract-mismatch}

**Symptom (logs):** `Detector weight contract: ... miss scoped labels` — `processor.detector_scope` lists a label the current binary weights do not provide (e.g. only `Bird` in the model while scope includes `Rodent`).

**Not a crash** when `processor.detector_weight_contract` is `warn` (default). In `enforce` mode startup fails until weights and scope align.

**What to do:** (1) Set `processor.detector_scope` to match `model.names` / your training manifest. (2) Or deploy weights that include every scoped label, then restart the processor. (3) Do not put `Background` in scope — see [CV_ML_PREP.md](../archive/internal/docs-legacy/CV_ML_PREP.md).

**Related:** [CV_ML_ROADMAP_PHASES.md](../archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.md) (#368).

---

## Recording: session summary JSON in logs {#recording-session-summary-json}

**Diagnose weak detections / empty DB rows:** after each clip finalize, processor logs one structured line:

`recording_session_summary {…}` (JSON) — `duration_s`, `triggered_camera`, `frames_seen`, `yolo_frames_ran`, `yolo_frames_with_tracks`, `low_light_blocked_frames`, `session_extended_by_frigate_only`, `bytetrack_rows`, `post_fusion_persisted`, `mqtt_events_in_window`, `video_file_ok`, `runtime_profile` (funnel: frames → YOLO runs → tracks → fusion).

**Example:** `docker logs birdlense 2>&1 | grep recording_session_summary | tail`

---

## Processor: slow frame warnings at high resolution {#processor-slow-frame-warnings}

**Symptom:** many lines `Slow frame processing: …ms >= …ms`; low FPS in summaries — common at **2.7K+** with heavy YOLO.

**Note:** `processor.frame_processing_warn_ms` (default **450**) only reduces **log noise**; it does not speed up inference. For **latency**, tune `processor.binary_imgsz`, profiles, or resources — see [PROCESSOR_PERFORMANCE.md](./processor-performance.md) and [RUNBOOKS.md](./runbooks.md). The System config-audit hint (`configAuditRuntimeSlowFrames`) explains the same trade-off.

---

## Slow web UI / API responses

**Common cause:** one container runs the **processor** (decode, detection, recording) and **gunicorn** (API). Under load the CPU is busy with frames and models, so UI requests wait in the gthread queue.

**What to try:**

1. **Docker resources** — default in `app/docker-compose.yml` is **4 CPUs / 4G RAM**. Raise `cpus` and `mem_limit` via `docker-compose.override.yml`.
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
nvidia-smi                           # на хосте
docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi   # в контейнере
```

Если не работает:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## Пустые записи (нет детекций)

1. RTSP поток работает? `ffplay rtsp://...`
2. Пути к ONNX файлам правильные? `ls -la app/processor/models/detection/trapper_ai_v02_2024/`
3. GStreamer pipeline корректный? (проверить в логах)

## Процессор не стартует (FileNotFoundError)

```bash
# Проверить пути в user_config.yaml
# Путь — относительно app/processor/
# Абсолютные пути должны существовать внутри контейнера
```

## Высокая загрузка CPU/GPU

- Уменьшить число RTSP потоков
- Проверить `binary_imgsz` в конфиге (640 рекомендуется)
- Убедиться, что NVDEC/NVENC используются (проверить логи GStreamer)

## Ошибка сборки Docker

```bash
docker build -f Dockerfile.orin -t birdlense-hub:orin . --no-cache
```

См. [`../TROUBLESHOOTING.md`](../TROUBLESHOOTING.md) · [`runbooks.md`](runbooks.md).