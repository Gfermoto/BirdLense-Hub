# BirdLense Hub configuration

[Русский](../ru/configuration.ru.md)

---

Config file: `app/app_config/user_config.yaml`

Defaults: `app/app_config/default_config.yaml`. User config is merged on top.

**Precedence:** `user_config.yaml` merges over `default_config.yaml`, then **runtime secret overlays** apply: if a `BIRDLENSE_*` variable below is set to a non-empty value, it replaces that key in the merged config (same effect as editing YAML, but without persisting to disk). Older single keys such as `GO2RTC_URL` still override `video.go2rtc_url` where documented.

### Merge, empty strings, and UI saves

- **Recursive merge:** user values override defaults. A key **missing** from `user_config` leaves the default in place.
- **Empty string is a value:** `some_key: ""` in `user_config` **clears** the default (it does **not** mean “fall back to default”). A common failure mode is `integrations.scales.mqtt_topic_prefix: ""`, which prevents derived `{prefix}/weight` subscriptions until you set `mqtt_topic` or remove the key.
- **Saving from the web UI** writes the **full merged tree** to `user_config.yaml`, not a minimal diff. That pins many keys: (1) the file grows over time; (2) upgrading `default_config.yaml` in a newer Hub release **does not** change keys already persisted in `user_config`; (3) secrets that reached the merged in-memory config via env could theoretically be written into YAML on the next save — in production prefer keeping secrets in **env** only, avoid unnecessary saves from the UI, or use only `BIRDLENSE_*` without duplicate secret keys in YAML.
- **Audit:** System → configuration audit (`GET /api/ui/system/config-audit`) includes MQTT feeder-scale checks (broker, prefix, explicit `""` keys in raw user YAML).

**UI:** Most options are editable in the web app (Settings → gear). YAML remains for advanced cases and env-based overrides.

**Related:** [ACCESS_CONTROL](../contributor/access-control.md) · [RU](../ru/access-control.ru.md) (password tiers), [API](../contributor/api.md) · [RU](../ru/api.ru.md) (HTTP surface), [GLOSSARY](./glossary.md) · [RU](../ru/glossary.ru.md) (terms). **Env file:** [`app/.env.example`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/.env.example) (copy for your install). **Contract:** [OpenAPI YAML](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/openapi.yaml).

**On this page:** [Environment variables](#environment-variables) · [Starter profiles](#starter-profiles) · [Minimal profile (no MQTT)](#minimal-profile-no-mqtt) · [Legacy `motion:` (deprecated)](#legacy-motion-block) · [Processor](#processor) · [Video](#video) · [Retention](#retention) · [Prometheus / Grafana](#prometheus--grafana) · [System page metrics](#system-page-metrics-history) · [Secrets](#secrets) · [See also](#see-also)

---

## Starter YAML profiles (`app/configs/`) {#starter-profiles}

Examples are **secret-free**; copy into `app/app_config/user_config.yaml` and add passwords/tokens via **env** or local YAML only.

| File | Typical use |
|------|-------------|
| [`minimal.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/minimal.yaml) | Go2RTC + OpenCV motion; **no MQTT broker**; YOLO/ByteTrack on camera path only |
| [`frigate-only.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/frigate-only.yaml) | MQTT triggers from Frigate only (no BirdNET topic) |
| [`full.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/full.yaml) | Reference “production-shaped” layout: several cameras, Frigate + BirdNET MQTT, HA weather, feeder — set `HA_TOKEN`, `MQTT_BROKER`, etc. in `.env` or YAML locally |

**Production vs file-replay test:** Normal operation uses `video.source: go2rtc`. For **offline mp4 replay**, set `video.source: file` with `file_dir` / `file_path` and tune `processor.file_max_record_floor_seconds` (see **Video** behaviour row). Use `processor.keep_recording_when_no_detections: true` only in this **file** mode if you need to keep sessions with **zero** detections (e.g. crops / QA). For **live / Go2RTC**, that flag is **ignored** — empty sessions are still removed to save disk (no change from pre-#264 behaviour). With **folder playlist** (`file_path` empty), the Hub **Library** page offers **File replay**: list/upload/delete clips under `file_dir`, start/stop and loop without restarting the container — the processor reads `data/file_test_control/desired.json` and writes progress to `status.json` ([#270](https://github.com/Gfermoto/BirdLense-Hub/issues/270)).

### Minimal profile — no MQTT broker {#minimal-profile-no-mqtt}

Frigate events, BirdNET-over-MQTT fusion, and binary PIR topics **require** a broker. If the broker is **down**, **not installed yet**, or you want **only** Go2RTC + OpenCV motion + local YOLO:

1. Start from **[`app/configs/minimal.yaml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/configs/minimal.yaml)** (copy or merge into `user_config.yaml`).
2. Keep **`mqtt.broker`** empty and **omit `MQTT_BROKER`** in **`app/.env`** (unless another feature needs it). The processor **does not** start the MQTT aggregator when the broker is unset — **Status** may show `mqtt: error` until you add a broker; **recording and YOLO** still run from the camera pipeline.
3. The sample **`triggers.*`** block matches runtime: OpenCV on, Frigate / motion_sensor / scales off.

### Legacy top-level `motion:` (deprecated) {#legacy-motion-block}

Older installs may still have a top-level **`motion:`** block in `user_config.yaml`. The hub **migrates** it into **`triggers.*`**, persists the file when possible, and logs a **WARNING** during that migration. Prefer **`triggers`** only in new YAML.

---

## How keys are named

- Tables use **dotted paths** that mirror YAML nesting, e.g. `video.go2rtc_url` → `video:` → `go2rtc_url:` in `user_config.yaml`.
- Boolean defaults like “empty password = open hub” are documented in [ACCESS_CONTROL](../contributor/access-control.md).

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATA_DIR` | Data directory (`/app/data` in Docker) |
| `REDIS_URL` | **`app/docker-compose.yml`:** defaults to `redis://redis:6379/0` (service `birdlense-redis`). **`docker-compose.image.yml`:** no Redis container — omit or point to an **external** Redis; otherwise the hub uses an **in-process** cache. Override in `app/.env` in any layout. **Host run without Compose:** unset → in-process cache. |
| `DATABASE_URL` | Optional. SQLAlchemy URI. Default: SQLite under `DATA_DIR`. For high write load use PostgreSQL, e.g. `postgresql+psycopg://user:pass@host:5432/dbname`. Operator runbook: [POSTGRES_MIGRATION](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/POSTGRES_MIGRATION.md). |
| `SQLALCHEMY_POOL_SIZE` | PostgreSQL pool size (default `5`) |
| `SQLALCHEMY_MAX_OVERFLOW` | PostgreSQL pool overflow (default `15`) |
| `FLASK_SECRET_KEY` | Flask session key (settings protection) |
| `FLASK_MAX_CONTENT_LENGTH` | Max HTTP body size in **bytes** for Flask/Werkzeug (default ~80 GiB in `web/config.py`). Your reverse proxy still needs its own upload limit (e.g. nginx `client_max_body_size`) for large Library uploads |
| `PROCESSOR_SECRET` | Processor API protection (`X-Processor-Token`) |
| `MCP_TOKEN` | MCP token (overrides `mcp.token`) |
| `BIRDLENSE_STRICT_API_AUTH` | `1` / `true` — in **production**, require auth for `/api/ui/*` (session after `verify-password`, `BIRDLENSE_UI_API_KEY`, or MCP Bearer); see [SECURITY](../contributor/security.md) |
| `BIRDLENSE_UI_API_KEY` | Secret for UI API in strict mode: header **`X-Birdlense-Api-Key`** or **`Authorization: Bearer`** (same value). Empty → session and MCP only |
| `BIRDLENSE_PORT` | Nginx port (default 8085) |
| `BIRDLENSE_HIDE_DIRECT_RECORDINGS` | `1` / `true` / `yes` / `on` — omit nginx `location` for `/data/recordings/` so anonymous **`GET /data/recordings/...`** falls through to **403**; playback remains **`/api/ui/videos/:id/stream`**. Default: direct static alias. **Public/VPS checklist:** [PUBLIC_RECORDINGS.md](./public-recordings.md). |
| `GUNICORN_THREADS` | Gunicorn `gthread` worker thread count (default **16**; `app/scripts/entrypoint.sh`) |
| `CORS_LOCAL_DEV_ORIGINS` | Local/dev CORS origins (comma-separated): Vite, `birdlense.local`, hub port. Default matches former in-code list; set empty to omit |
| `CORS_DEFAULT_ORIGINS` | Baseline CORS origins (comma-separated) for non-localhost defaults |
| `CORS_ORIGINS` | Extra CORS origins (comma-separated) |
| `TRUSTED_PROXY` | `1` / `true` — honor `X-Real-IP` / `X-Forwarded-For` for rate limiting behind a **trusted** reverse proxy; see Webhook § and [SECURITY](../contributor/security.md) |
| `OPENWEATHER_API_KEY` | OpenWeather key |
| `XENO_CANTO_API_KEY` | Xeno-canto v3 key for species song audio in the UI. `BIRDLENSE_XENO_CANTO_API_KEY` still overrides `secrets.xeno_canto_api_key` after YAML merge |
| `MQTT_BROKER`, `MQTT_PASSWORD` | MQTT if not in config |
| `HA_URL`, `HA_TOKEN` | Home Assistant base URL and long-lived token when not only in YAML (`homeassistant.*`) |
| `GO2RTC_URL` | Go2RTC URL if not in config |
| `HF_TOKEN` | Optional Hugging Face token for **`huggingface-cli`** / dataset tooling — **not** read by the Hub web process (see `app/.env.example`) |
| `BIRDLENSE_STARTUP_BACKFILL_SPECIES_TAXA` | `1` — run species→taxon backfill on app startup; default off; otherwise use `POST /api/ui/system/species-registry/backfill` |
| `BIRDLENSE_STARTUP_CLEANUP_LEGACY_IMPORT` | `1` — remove legacy disk-import placeholder detections on startup; default off; recording scan still cleans |
| `BIRDLENSE_STARTUP_REPAIR_SPECIES_METADATA` | `1` — background metadata/image repair on startup; default off |
| `BIRDLENSE_NOTIFY_APP_STARTUP` | `0` — skip Telegram “App is UP!” on startup; default on |
| `BIRDLENSE_INFERENCE_BACKEND` | Overrides `processor.inference_backend` (`torch`, `openvino`, …) — see [CV_ML_ROADMAP_PHASES](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.md) |
| `BIRDLENSE_INFERENCE_DEVICE` | Overrides `processor.inference_device` (`auto`, `cpu`, `cuda`, `intel:gpu`, …) |
| `BIRDLENSE_BINARY_OPENVINO_PATH` | Optional path to OpenVINO IR (directory or `.xml`) for the binary detector; highest precedence over YAML when set |
| `BIRDLENSE_OPENVINO_PROFILE` | OpenVINO performance profile (`latency` or `throughput`) |
| `BIRDLENSE_OPENVINO_NUM_REQUESTS` | OpenVINO async requests (`0` = runtime auto) |
| `BIRDLENSE_INFERENCE_AUTO_BENCHMARK` | `1` / `true` / `yes` / `on` — after the detection stack loads, run one blank-frame `predict` on the binary detector and record **`cold_start_predict_ms`** in `data/processor/inference_backend_cache.json` ([#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371)) |
| `BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC` | System page resource sampler interval (seconds); default `30`; allowed 10–600 — see [§ System page metrics history](#system-page-metrics-history) |
| `BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS` | Keep `system_resource_sample` rows up to this age (hours); default `72`; allowed 6–720 |
| `DISABLE_SYSTEM_METRICS_SAMPLER` | `1` / `true` — disable the background sampler (tests, CI) |
| `BIRDLENSE_METRICS_TOKEN` | If set, `GET /metrics`, `/api/metrics`, `/api/metrics/summary` require `Authorization: Bearer` — see [§ Prometheus / Grafana](#prometheus--grafana) |
| `BIRDLENSE_TELEGRAM_BOT_TOKEN` | Overrides `notifications.telegram_bot_token` |
| `BIRDLENSE_TELEGRAM_MTPROTO_SECRET` | Overrides `notifications.telegram_mtproto_secret` |
| `BIRDLENSE_TELEGRAM_API_HASH` | Overrides `notifications.telegram_api_hash` |
| `BIRDLENSE_HA_TOKEN` | Overrides `homeassistant.token` |
| `BIRDLENSE_SETTINGS_PASSWORD` | Overrides `general.settings_password` (plaintext or bcrypt hash) |
| `BIRDLENSE_CONTRIBUTOR_PASSWORD` | Overrides `general.contributor_password` (plaintext or bcrypt hash) |
| `BIRDLENSE_MQTT_PASSWORD` | Overrides `mqtt.password` |
| `BIRDLENSE_GO2RTC_PASSWORD` | Overrides `video.go2rtc_password` |
| `BIRDLENSE_OPENWEATHER_API_KEY` | Overrides `secrets.openweather_api_key` |
| `BIRDLENSE_EBIRD_API_KEY` | Overrides `secrets.ebird_api_key` |
| `BIRDLENSE_XENO_CANTO_API_KEY` | Overrides `secrets.xeno_canto_api_key` |
| `BIRDLENSE_MCP_TOKEN` | Overrides `mcp.token` |
| `BIRDLENSE_VAPID_PRIVATE_KEY` | Overrides `web_push.vapid_private_key` |
| `BIRDLENSE_REDIS_URL` | Overrides `performance.redis_url` |
| `BIRDLENSE_RECORDINGS_MIRROR_SFTP_PASSWORD` | **Optional runtime override** of `storage.recordings_mirror.sftp_password` (normally set in **Library → Storage** or `user_config.yaml`) |
| `BIRDLENSE_RECORDINGS_MIRROR_SFTP_KEY_PASSPHRASE` | **Optional runtime override** of `storage.recordings_mirror.sftp_key_passphrase` |

**NAS / SFTP mirror (recordings):** Configure mirror host, user, password, and options in the hub UI (**Library → Storage**, admin) or in `user_config.yaml`; secrets are masked in `GET /api/ui/settings` like other hub secrets. Saving requests a **processor restart** (flag) so the processor process reloads config, and **Test connection** validates SFTP access to the remote directory. With `storage.recordings_mirror.enabled: true`, the processor uploads each saved session folder to SFTP in the background after finalize. Paths in the database stay `data/recordings/...`; the hub still serves video from local disk unless you enable **`delete_local_after_success`** (expert-only). **Alternative:** mount NAS at `DATA_DIR` / bind-mount `recordings/` — no SFTP code path. See [INSTALL.md](./install.md) data paths.

**UI passwords:** values saved from Settings are stored as **bcrypt** hashes in `user_config.yaml` when you enter a new plaintext; existing **plaintext** entries still work until changed. Env may supply either plaintext or an existing bcrypt string.

See `app/.env.example`. Secrets are generated by `make setup` (via `make start` / `make pull`).

---

## General

| Key | Description |
|-----|-------------|
| `settings_password` | **Admin** password: settings, feeder dispense, system tools, processor restart. Empty = no lock (home lab default) |
| `require_auth_for_video_stream` | **`false`** (default): guests can play recordings (`/api/ui/videos/:id/stream`), consistent with [ACCESS_CONTROL](../contributor/access-control.md). **`true`**: stream requires Contributor/Admin (legacy lock-down). **Public hub:** decide together with [PUBLIC_RECORDINGS.md](./public-recordings.md). |
| `contributor_password` | Optional **Contributor** password: species fixes, Unknowns, iNaturalist, dataset export, reports — **not** settings/feeder/system. Empty = single-tier mode (see [ACCESS_CONTROL](../contributor/access-control.md)) |
| `session_idle_minutes` | Drop login session (admin/contributor) after **N** minutes without `/api/*` requests. **0** disables. Default **30**. Applies when either password is set or production runtime; see [SECURITY](../contributor/security.md). |
| `enable_notifications` | Enable notifications (global) |
| `notification_excluded_species` | Species excluded from notifications |
| `birdnet_url` | Link to your audio stack’s web UI (BirdNET-Go, BirdNET-Pi, etc.). Empty = footer link/icon hidden. Merge settings do **not** depend on which build you use — MQTT payload matters. |
| `donate_url` | Support link. When non-empty, only the heart icon in the top app bar is shown. Empty = hidden. |

**Platforms:** RU — [Boosty](https://boosty.to), [DonationAlerts](https://donationalerts.com), [DONAT24](https://donat24.ru), YooMoney. Elsewhere — Ko-fi, GitHub Sponsors, Patreon. Settings → General → paste page URL.

### Heimdall widgets for Hub metrics

- Heimdall stays a **manual dashboard** for BirdLense URLs and metric endpoints.
- Add tiles that point directly to your hub, for example:
  - Prometheus text: `http://<hub-host>:<port>/metrics` or `/api/metrics`
  - JSON snapshot (same counters as Prometheus): `http://<hub-host>:<port>/api/metrics/summary`
- BirdLense no longer stores a dedicated `heimdall_url` or probes Heimdall from the server side.

The System page also lists these endpoints under **Notification observability** (authenticated UI).

**Heimdall dashboard:** URL checklist and manual tile setup (Heimdall v2 has no bulk import in the UI) — [HEIMDALL](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/HEIMDALL.md).

---

## Processor

| Key | Description |
|-----|-------------|
| `tracker` | Tracker config (`bytetrack.yaml`) |
| `max_record_seconds` | Max recording length (seconds) |
| `max_inactive_seconds` | Max gap without detections |
| `post_record_seconds` | Post-roll: added to the no-detection gap before stopping the clip. Effective gap = `max_inactive_seconds` + `post_record_seconds`. See [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157). |
| `min_seconds_between_recordings` | Minimum pause after a clip ends before a new one may start. Default `8`. Helps suppress near-duplicate clips when the bird stays in frame or Frigate/OpenCV retrigger immediately. `0` disables the cooldown. |
| `min_confidence_binary` | Detector threshold: bird vs non-bird. Default **0.30** (`default_config.yaml`) |
| `min_confidence_binary_bird` | Optional: stricter **Bird-only** threshold after `track()` (Ultralytics uses `min` of all thresholds; per-label filter in Python). Example: **0.48** with `min_confidence_binary_rodent: 0.22` cuts false “birds” (e.g. mouse→tit) without choking rodents. |
| `min_confidence_binary_rodent` | Optional: threshold for **Rodent** boxes after the binary head normalizes the rodent class (YOLO weights may still use an internal “Squirrel” class name). |
| `min_confidence_binary_squirrel` | **Deprecated:** if present after merge, its value is **copied into** `min_confidence_binary_rodent` (so legacy YAML keeps working; remove squirrel once you use rodent only). |
| `bird_skip_classifier_max_area_frac` | If **> 0**: for **Bird** with bbox area ≤ this fraction of the frame, **skip** species classifier → generic Bird only (reduces bogus species on tiny blobs). Default **0** (off). Try **0.012–0.025**; too high hurts small tits at the feeder. |
| `min_track_duration` | Min **YOLO/ByteTrack** track length (s) to keep a `video` detection. Applies before fusion. Raise it if you get flicker; lower it if short perch visits disappear. |
| `min_confidence_to_process` | Species-classifier threshold after detector confirmation. Default **0.40**. Lower = more accepted species, higher = stricter. |
| `min_confidence_to_notify` | Minimum combined confidence for **Telegram photo alerts** (after the hub accepts the recording). Shipped default **0.46** in `default_config.yaml`; `app_config.CONFIDENCE_FLOORS` enforces a **minimum of 0.30** at load time (values below are raised). Often set **above** `min_confidence_to_process` to reduce chat noise while still persisting visits. Exposed in **Settings → Processor**. After changing YAML thresholds, **restart the processor** so the running process reloads config. |
| `species_confidence_overrides` | Per-species thresholds: `{"Rodent": 0.28}` for rodents; `{"Rare Bird": 0.05}` for rare birds |
| `ebird_regional_top_auto_confidence` | If true (default), merge lower thresholds for species in the regional eBird top (needs `secrets.ebird_api_key`, `ebird.*`). Manual `species_confidence_overrides` keys always win. See [#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128). |
| `ebird_regional_top_confidence_delta` | Subtracted from `min_confidence_to_process` for each auto top species (default `0.03`). |
| `ebird_regional_top_confidence_floor` | Minimum auto threshold (default `0.08`). |
| `birdnet_mqtt_auto_confidence` | If **true**, lower classifier thresholds for species seen in **recent** BirdNET MQTT messages (similar to eBird top). BirdNET is **confidence-only** here: it never creates a final video label. Manual `species_confidence_overrides` win. See [#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129). |
| `birdnet_mqtt_bias_delta` | Subtracted from `min_confidence_to_process` for auto BirdNET species (default `0.05`). |
| `birdnet_mqtt_bias_floor` | Minimum auto threshold for BirdNET bias (default `0.05`). |
| `multi_camera_groups` | List of Frigate camera-id groups at one location, e.g. `[["BirdBox","Forest"]]`. See [#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153). |
| `multi_camera_confidence_boost` | When Frigate reports the **same species** from **two or more** cameras in one group, add this to merged `confidence` (default `0.03`, capped at 1.0). |
| `spectrogram_px_per_sec` | Mel-spectrogram horizontal resolution (pixels per second of audio). |
| `generate_spectrogram_always` | Default **true**: build `spectrogram_*.jpg` after **every** finalized recording (FFmpeg + librosa). **false**: only when a BirdNET MQTT event falls inside the recording window (less CPU). |
| `regional_species` | Optional classifier narrowing list (empty = classifier can use all classes). |
| `detector_scope` | First-stage detector targets. Default: `["Bird", "Rodent"]`. EU classifier non-bird class **Rodent** is the catalog name; raw detector weights may still label that head “Squirrel”, which the hub maps to **Rodent**. Background / hard-negative detector classes must stay outside this scope; see [CV / ML prep contract](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/CV_ML_PREP.md). |
| `classifier_fallback_bird` | Keep the generic detector label when the detector confirmed a target but the classifier stayed below threshold. Frigate may still promote that fallback label later if it has a matching species/sub-label. |
| `included_bird_families` | Bird family filter list (e.g. Perching Birds); not related to Rodent |
| `save_images` | Save detection frames |
| `detection_strategy` | Production runtime uses `two_stage` only. Other values (including old `single_stage`) are ignored with a warning; remove them from `user_config.yaml` before CV / ML rollout work. |
| `models.binary` | Binary detector path (`.pt`) |
| `models.classifier` | Classifier path (`.pt`) |
| *(custom weights)* | **System → Processor weights** ([#276](https://github.com/Gfermoto/BirdLense-Hub/issues/276)): upload writes `binary.pt` / `classifier.pt` / `class_names.txt` under **`DATA_DIR/custom_weights/`** and sets **absolute** paths in `user_config` (relative paths here resolve from `app/processor`, not from `DATA_DIR`). After upload/reset the hub sets the processor restart flag. |
| `file_max_record_floor_seconds` | **`video.source=file` only:** minimum wall-clock segment (seconds) before finalize can split a long clip; default **86400**. See **Video** behaviour row. |
| `keep_recording_when_no_detections` | **`video.source=file` only** (default **false**). If **true**, keep the finalized session (valid mp4) when there were **zero** stored detections — useful for offline pipelines. For **`go2rtc` / live** this key has **no effect**; empty sessions are still deleted. |
| `track_regen_parallel_auto_with_manual` | Advanced track-regeneration parallelism when mixing auto and manual scope; ops tuning, YAML-only (see System → track regen docs in UI). |

---

## Video

| Key | Description |
|-----|-------------|
| `source` | `go2rtc` or `file` (test: mp4 folder or single path in container) |
| `file_path` | Single mp4 absolute path in container; empty with `file_dir` for playlist |
| `file_dir` | Folder with `*.mp4` / `*.mov` / `*.mkv` (flat list, not recursive). Default in repo: **`/app/data/file_test`** (Docker: host `./data` → `/app/data`). |
| `file_loop` | Replay playlist/file in a loop (Library **File replay** card writes this when you enable `source=file`; loop can be toggled in the same card while the processor runs) |
| `file_realtime_simulation` | **`video.source=file` only** (default **false**). **true** — advance frames on **wall-clock** time vs clip FPS (mimics real-time playback; **drops frames** if the pipeline lags). **false** — one frame per `capture()` (fast-forward, easier debugging). UI: **Settings → Connections → File replay (processor)**. |
| `file_test_max_upload_mb` | Max MiB per clip uploaded via Hub (**Library** → file replay). Clamped **64–65536** in code; default **10240** (>10000 MiB). A reverse proxy may return **413** before Flask — set e.g. nginx `client_max_body_size` ≥ your largest clip. Flask body cap: env **`FLASK_MAX_CONTENT_LENGTH`** (bytes); default in `web/config.py` is large so the YAML limit applies first. |
| *(behaviour)* | For **`video.source=file`** with a **folder playlist**, each **`VideoPlaylistSource`** clip triggers a **session finalize** when the file ends (crops/DB/notifications for that clip), then the next file continues in a new session. **`processor.max_inactive_seconds`** is floored to **120**s. **`processor.file_max_record_floor_seconds`** (default **86400**) is a wall-clock safety minimum for **`max_record_seconds`** so long files are not cut mid-clip by the live-camera default; lower it only if you want time-based splits. |
| `go2rtc_url` | Go2RTC URL (`http://YOUR_HOST:1984`) |
| `cameras` | List: `{id, stream_name, name}` |
| `pre_record_seconds` | Pre-roll before trigger |
| `auto_reconnect` | Auto-reconnect to stream |
| `video_width`, `video_height` | Resolution |

---

## Motion

| Key | Description |
|-----|-------------|
| `source` | `opencv` \| `frigate` \| `mqtt` \| `esphome` |
| `frigate_camera_filter` | Frigate cameras (from `cameras`) or empty = all |
| `frigate_label_filter` | Frigate labels that may trigger recording (`bird`, `Bird`, `squirrel`, `Squirrel` by default). Triggering does **not** assign the final label on its own. |
| `frigate_label_exclude` | Labels to ignore (cat, dog — mouse as cat) |
| `mqtt_topic` | MQTT binary sensor topic (Tasmota PIR) |
| `esphome_url` | ESPHome URL |
| `esphome_sensor_id` | `binary_sensor` id in ESPHome |

---

## MQTT

One connection — Frigate and BirdNET topics. Triggers: Frigate, ESPHome, MQTT binary, OpenCV, and other motion/event sources. Final labels still come from the shared detector/classifier fusion path.

| Key | Description |
|-----|-------------|
| `broker` | Broker address |
| `port` | Port (1883) |
| `frigate_topic` | Frigate events topic |
| `birdnet_topic` | BirdNET topic |
| `publish_topic` | BirdLense detection publish topic |
| `reconnect_min_delay` | Minimum MQTT reconnect/backoff delay (seconds) |
| `reconnect_max_delay` | Maximum MQTT reconnect/backoff delay (seconds) |
| `publish_queue_max` | Cap for outbound MQTT publish queue inside the processor (default **4000** in `default_config.yaml`; flush after reconnect). Related gauges: `mqtt_outbound_queue_depth`, `mqtt_outbound_drops_total`, `mqtt_outbound_publish_errors_total`. See [PROCESSOR_PERFORMANCE](./processor-performance.md#queues-backpressure). |
| `ha_discovery` | Home Assistant MQTT discovery for BirdLense entities. Default true. Observe-only: last species / confidence / detection time, feeder presence, current feeder weight (when scales use MQTT), and related availability/device metadata. |

**Topics:** `frigate/events` (Frigate), `birdnet` (BirdNET), `birdlense/detections` (publish), `birdlense/sensor/last_species/state` (HA), `birdlense/binary_sensor/bird_detected/state` (HA), `birdlense/sensor/feeder_weight/state` (HA), `birdlense/binary_sensor/feeder_bird_present/state` (HA). Feeder relay: `homeassistant/switch/bird_feeder/command`.

**BirdNET (any common build):** the processor accepts several field layouts — notably **BirdNET-Go** (`CommonName`, `ScientificName`, `SpeciesCode`, `Confidence`, `BeginTime`, optional `BirdImage.URL`) and **BirdNET-Pi** (`Common_Name`, `Confidence_Score`, `Date`, etc.). You do **not** pick “Go vs Pi” in config: JSON must arrive on `mqtt.birdnet_topic`. **Video merge and FIFO priors** use the Hub’s **canonical species name**: when the payload includes a **scientific name** (Go usually does), the **MQTT display language** (EN/RU, …) does not break matching; without it, use **species aliases** in the registry and/or `detection.species_mapping`. If the Hub runs on **PostgreSQL only** without a shared `birdlense.db` file, automatic catalog matching from that SQLite path is unavailable — rely on YAML mapping. BirdNET remains **confidence-only** for the final video label. **Frigate:** `after` — `camera`, `label`, `sub_label` (species from Bird Classification), `frame_time`. `sub_label` wins over `label` and may promote a generic detector fallback when the video detector already confirmed a target.

**Missed-event note:** during outages, MQTT events can be missed and are usually not replayed later (Frigate events are typically a live stream, not backlog replay). Use Frigate recording/clip retention as the source of historical truth.

**Operator metrics:** `data/diagnostics/processor_runtime_stats.json` exposes trigger/MQTT degradation gauges (`trigger_*`, `mqtt_connected`) — see [PROCESSOR_PERFORMANCE](./processor-performance.md) § Trigger path observability.

---

## Feed

| Key | Description |
|-----|-------------|
| `source` | `mqtt` \| `esphome` |
| `duration_seconds` | Relay on duration |
| `mqtt_topic` | MQTT relay topic (Tasmota) |
| `esphome_url` | ESPHome URL |
| `esphome_switch_id` | Switch/button id |
| `esphome_type` | `switch` \| `button` |

**Last dispense:** Hub writes `data/feed_last_dispense.json` on successful dispense. Overview feeder card shows last dispense time.

---

## Home Assistant (REST API)

Shared **URL** and **Long-Lived Access Token** for any feature that calls the Home Assistant REST API: weather (when `weather.source` is `homeassistant`), feeder scale when `integrations.scales.source` is `homeassistant`, and future integrations. **Environment:** `HA_URL` and `HA_TOKEN` override the YAML fields when set.

| Key | Description |
|-----|-------------|
| `homeassistant.url` | Base URL (e.g. `http://homeassistant:8123`) |
| `homeassistant.token` | Long-Lived Access Token (masked in API) |

**Deprecated (still read as fallback):** `weather.ha_url`, `weather.ha_token` — migrate to `homeassistant.*`; System config audit may flag them.

---

## Weather

| Key | Description |
|-----|-------------|
| `source` | `openweather` \| `homeassistant` |
| `ha_entity_id` | When `source` is `homeassistant`: which `weather.*` entity to read (e.g. `weather.home`). URL and token are **not** here — use `homeassistant.*` above. |

---

## Detection (shared fusion path)

**Production path:** trigger source -> detector (`Bird | Rodent`) -> YOLO species classifier -> fusion -> persistence.

**Source semantics:**
- YOLO detector/classifier is the primary source of every persisted video detection.
- Frigate is a helper source: it can promote a generic detector fallback or add a confidence boost when it agrees with the video track.
- BirdNET is confidence-only for video. It can bias thresholds before the classifier decision but does not create a final video label.

**Recall-first feeder profile:** when you care more about not missing small birds than minimizing false positives, enable Frigate as a trigger (**`triggers.frigate.enabled`**) when MQTT is available, keep **`triggers.opencv.check_every_n_frames=1`** (optional OpenCV alongside), and use `processor.binary_imgsz=640`, `processor.min_center_dist=0.03-0.05`, `processor.min_box_size_px<=64`. In low light, relax the light gate instead of disabling detection entirely.

**Canonical names:** Common name (Eurasian Jay), not scientific. `species_mapping` maps variants. `species_canonical_mapping.txt` for “Merge duplicates” (System → Recordings). Format: `variant|canonical`.

**Catalog quality:** `app/web/seed/species_suspect_blocklist.txt` lists terms used to hide non-bird / object rows from filtered species pickers (`GET /api/ui/species?exclude_suspects=1` when requested). Full report (suspects, duplicate-name merge candidates): System → “Species catalog data quality” or `GET /api/ui/system/species-registry/data-quality` (settings password). New ingest matching the blocklist does not create a junk species row — it is routed to “Unknown”.

**Classifier dataset alignment (EU ~491 / US NABirds ~400):** in `user_config.yaml`, `species.catalog_allowlist_file` points to a text file of class display names (one per line, same as merged_cls / YOLO-normalized). Generate from your `best.pt` (or other `.pt`) with `scripts/datasets/dump_classifier_allowlist.py` (e.g. write `models/classification/weights/class_names.txt` under `app/processor`). Set `species.catalog_strict_ingest: true` to block new species outside that list (detections go to “Unknown”). Bulk cleanup of existing junk and duplicate names: `POST /api/ui/system/species-catalog/reconcile` (always try `{"dry_run": true}` first). Compare classifier vs DB vs `data/dataset` folders: System → “Classifier vs catalog vs dataset”.

**Classifier output vs DB / manual names:** Automatic labels are only strings that exist in the trained head inside the `.pt` (the merged class list). Adding a row in the SQLite species table or fixing text in the UI does **not** create a new classifier output — for example there is no “chicken” label unless that exact class name was trained in. Use the allowlist file to stay aligned with the model; to add new auto species, retrain or swap weights ([TRAINING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/TRAINING.md)).

**Unknowns UX:** With strict ingest, out-of-allowlist names are stored against **Unknown** (no new species row). Contributors fix labels in **Unknowns**; operators use System → species data quality / reconcile for bulk cleanup. Display names for the same taxon should follow **canonical** rules above (`species_mapping`, `species_canonical_mapping.txt`, merge duplicates).

| Key | Description |
|-----|-------------|
| `merge_window_seconds` | MQTT merge window (8 s) |
| `dedup_window_seconds` | Gap > N s = new visit (60 s) |
| `one_per_species` | One result per species (true) |
| `source_priority` | Conflict resolution order for fused sources. Default production order: `["yolo", "frigate"]`. |
| `cross_source_confidence_bonus` | When Frigate first confirms an existing YOLO detection, add this to confidence once (cap 1.0). Set `0` to disable. |
| `min_confidence_to_store` | Min fused confidence to persist (default **0.30**). Also used as the floor for detector-label fallbacks. |
| `species_mapping` | Species name mapping |

**Fusion trace (UI):** On the video page, **Fusion trace** loads the latest processor `decision_trace` row from ActivityLog (matched by `video_id` in the payload after ingest, or legacy match on `video_path`). Stages shown per track: **detector** (YOLO generic label and confidence), **classifier** (species head, vote share, threshold), **scores** (frame evidence, trust band, reject reason), **audio** (BirdNET alignment), **fusion** (multi-camera / Frigate flags), **outcome** (species and confidence stored on the clip). API: `GET /api/ui/videos/{video_id}/fusion-trace` — **contributor or admin session only** (not anonymous viewers).

**Inference backend & detector weight contract (CV/ML):** `processor.inference_backend` is `torch` (default) or `openvino` for the binary detector via Ultralytics OpenVINO export ([#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371)). `BIRDLENSE_INFERENCE_BACKEND` overrides YAML. For `openvino`, set `processor.models.binary_openvino` to the export directory or `.xml`, or set `BIRDLENSE_BINARY_OPENVINO_PATH` (absolute or relative to the processor package root). Classifier weights stay PyTorch `.pt`. `processor.detector_weight_contract` is `off` \| `warn` \| `enforce` and validates loaded detector `model.names` against `processor.detector_scope` ([#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368)). Phase overview: [CV_ML_ROADMAP_PHASES.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.md).

**EU model:** `best.pt` from [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) (default `processor.models.classifier`). US: `best_US.pt`. Training: [TRAINING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/TRAINING.md).

## Retention

| Key | Description |
|-----|-------------|
| `days` | Delete recordings older than N days |
| `max_gb` | Max size in GB (optional) |

---

## Integrations (scales)

**Sources and capabilities:** `mqtt` is the **MQTT-backed** mode: the **processor** subscribes to weight topics, writes `feeder_scale_state.json` / `feeder_scale_history.jsonl`, can **estimate per-clip delta**, and can optionally **start recording** on a weight spike. `esphome` polls the device over the ESPHome Web API and is intended for **live weight / bird_present / tare only**. History / delta / motion-trigger options apply only to `mqtt`.

| Key | Description |
|-----|-------------|
| `integrations.scales.enabled` | Feeder / smart-scale weight path (default **false**). |
| `integrations.scales.source` | `mqtt` (default) — firmware topics / manual MQTT setup; `esphome` — ESPHome Web API (live weight / bird_present / tare only). |
| `integrations.scales.mqtt_topic` | Full MQTT topic for **weight** (plain number or JSON with `value` / `weight` / `state`). If **empty** and `mqtt_topic_prefix` is set, the processor uses **`{prefix}/weight`**. |
| `integrations.scales.mqtt_bird_present_topic` | Optional full topic for **bird on platform** (`ON`/`OFF` or HA-style state). If **empty** and `mqtt_topic_prefix` is set, the processor uses **`{prefix}/bird_present`**. Use when weight is on e.g. `homeassistant/sensor/.../state` but presence is still published on the device prefix. |
| `integrations.scales.mqtt_topic_prefix` | Optional prefix: **`{prefix}/weight`** when `mqtt_topic` is empty; **`{prefix}/bird_present`** when `mqtt_bird_present_topic` is empty; tare publishes to **`{prefix}/command`** unless `mqtt_command_topic` is set. Stock repo ESPHome sketch: **`birdlense/scale`** (`esphome/bird-feeder-scale.yaml`). |
| `integrations.scales.mqtt_command_topic` | Optional full command topic (overrides `{prefix}/command`). Also in Settings → Video (scales). |
| `integrations.scales.mqtt_tare_payload` | String published for tare (default **`TARE`**). Your device must subscribe on the command topic if you use the Hub button. |
| `integrations.scales.esphome_url` | Base URL for direct ESPHome Web API mode, e.g. `http://192.168.1.50`. |
| `integrations.scales.esphome_weight_sensor_id` | ESPHome `sensor` id for weight in `esphome` mode. Default: `weight_live_internal`. Hub reads `GET /sensor/<id>`. |
| `integrations.scales.esphome_bird_present_sensor_id` | Optional ESPHome `binary_sensor` id for bird presence in `esphome` mode. Default: `bird_present`. Hub reads `GET /binary_sensor/<id>`. |
| `integrations.scales.esphome_tare_button_id` | Optional ESPHome `button` id for tare in `esphome` mode. Default: `manual_tare`. Hub calls `POST /button/<id>/press`. |
| `integrations.scales.weight_estimate_enabled` | When **true** (default), the processor may store a **weight delta for the recording window** on the video row. **Independent** of `motion_trigger_enabled`: you can estimate weight on clips started by Frigate/motion without auto-start from scales. Requires `mqtt` and `feeder_scale_history.jsonl` under `DATA_DIR`. The delta is **not** saved when the clip only has BirdNET rows (`source=audio`) with no frame/track: audio helps species ID; it is not tied to feeder weight. |
| `integrations.scales.min_delta_kg_for_estimate` | Minimum delta (kg) for both the **window span** (max−min) and the **spike** between consecutive time-ordered MQTT samples. Default **0.008** (~8 g). |
| `integrations.scales.estimate_require_consecutive_spike` | **true** (default): persist an estimate only if some **adjacent** sample pair in the clip has \|Δ\| ≥ `min_delta_kg_for_estimate` (reduces slow drift when the platform reads near zero after tare). **false**: legacy span-only check. The stored value remains **max−min** over the window. |
| `integrations.scales.history_max_lines` | Max lines for the sample log (head trimmed); default **10000**. |
| `integrations.scales.motion_trigger_enabled` | **false** by default. **true** — a sharp weight change on the scale MQTT topic **starts the same recording + YOLO pipeline** as other enabled triggers (**OR** with Frigate and optional OpenCV when those toggles are on). Frigate/BirdNET events in the clip window are still merged via `merge_detections`. Requires `mqtt.broker`, MQTT-capable scales source, and a weight topic (**`mqtt_topic`** or **`{mqtt_topic_prefix}/weight`**). Prefer **`triggers.scales.enabled`** in new configs; hub still falls back from `integrations.scales.motion_trigger_*` when building effective triggers. |
| `integrations.scales.motion_trigger_min_delta_kg` | Minimum absolute weight change (kg) between **two consecutive** MQTT samples to fire the trigger. Default **0.02**. |
| `integrations.scales.motion_trigger_debounce_seconds` | Minimum seconds between recording starts triggered by scales. Default **1.5**. |

The processor compares min/max scale readings between `start_time` and `end_time`. With **`estimate_require_consecutive_spike: true`** (default), a value is persisted only if some adjacent sample pair in that window has a step ≥ the threshold (see key above), while the stored metric remains the max−min span. When the span meets the threshold, `scales_weight_delta_kg` is saved and the video page shows a compact “Scales (estimate)” block. Notification triggers and auto-tare in HA/ESPHome remain in [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167).

**Stack like [ESPHome + Home Assistant smart scale](https://github.com/igiannakas/Homeassistant-scale-with-auto-tare-and-object-detection?tab=readme-ov-file#hardware-setup)** (HX711, ESP32, proximity, auto-tare in HA): BirdLense can be wired two ways:
- `mqtt`: subscribe the processor to the firmware weight topics
- `esphome`: poll the device over ESPHome Web API for live weight / bird_present / tare

**BirdLense ESPHome MQTT firmware (repo `bird-feeder-scale.yaml`):** use `source: mqtt`. By default, `mqtt_topic_prefix: birdlense/scale` is enough; the hub derives **`birdlense/scale/weight`**, **`birdlense/scale/bird_present`**, and **`birdlense/scale/command`** automatically. If you need a mixed layout, keep `source: mqtt` but override `mqtt_topic`, `mqtt_bird_present_topic`, or `mqtt_command_topic` explicitly.

### ESPHome / custom firmware (`birdlense/scale/*`)

For a **dedicated topic family** (weight + bird presence + optional command), set **`integrations.scales.mqtt_topic_prefix`** to e.g. **`birdlense/scale`** (this is already the default), leave **`mqtt_topic`** empty, and point the device at the same broker as the Hub.

| Topic | Payload | Retain (typical) | Hub behavior |
|-------|---------|------------------|----------------|
| `{prefix}/weight` | Float string (grams or your unit per `unit` key) | yes | Updates `feeder_scale_state.json`, appends history, optional motion trigger |
| `{prefix}/bird_present` | `ON` / `OFF` | yes | Merges into `feeder_scale_state.json` as `bird_present` (Overview feeder card) |
| `{prefix}/command` | e.g. `TARE` | no | Published by **`POST /api/ui/feed/scale-tare`** (admin); firmware must subscribe if you use tare from the Hub |

**Firmware note:** publish weight as a **plain decimal string** (not a C struct). In ESPHome, use e.g. `str_sprintf` in the `mqtt.publish` payload lambda. Subscribe to `{prefix}/command` for tare (BirdLense sends **`mqtt_tare_payload`**, default `TARE`).

**Example firmware** in the repository: [`esphome/bird-feeder-scale.yaml.example`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/esphome/bird-feeder-scale.yaml.example) (copy to `bird-feeder-scale.yaml` locally) and [`esphome/README.md`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/esphome/README.md).

---

## Notifications (Telegram)

| Key | Description |
|-----|-------------|
| `general.enable_notifications` | Enable notifications |
| `notifications.telegram_bot_token` | Bot token (@BotFather → `/newbot`) |
| `notifications.telegram_chat_id` | Chat or channel id (e.g. `-1001234567890`) |
| `notifications.base_url` | Hub URL for video/Live links. If empty, relative links cannot be turned into a full URL and Telegram link previews become less useful |
| `notifications.telegram_proxy_type` | `none` — no proxy; `socks_http` — URL below (typical); `mtproto` — server/port/secret like the Telegram app + **api_id/api_hash** |
| `notifications.telegram_proxy_url` | With `socks_http`: proxy for Bot API (`socks5h://…`, `http://…`). Empty = direct. Web image includes `requests[socks]`. |
| `notifications.telegram_mtproto_host` / `telegram_mtproto_port` / `telegram_mtproto_secret` | Only for `mtproto`; secret is hex from the Telegram app |
| `notifications.telegram_api_id` / `telegram_api_hash` | Only for `mtproto`; from **https://my.telegram.org** → API development tools (or env `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`) |
| `notifications.telegram_api_base` | Empty = `https://api.telegram.org`; or your HTTPS reverse proxy base |
| `notifications.telegram_timeout` | Max timeout seconds for Telegram requests (text uses half) |
| `notifications.telegram_retries` | Retry count on timeout/connection errors |
| `notifications.compress_photo_over_kb` | Compress JPEG when larger than N KB (0 = off) |
| `notifications.telegram_max_side_px` | Max image side in px before send (0 = no resize) |
| `notifications.message_thread_id` | Forum topic id |
| `notifications.disable_notification` | Silent messages |
| `notifications.protect_content` | Disallow forward/save |
| `notifications.link_preview_large` | Large link previews (Bot API 9.4). This complements photo delivery; it does not replace `sendPhoto` |
| `notifications.use_custom_emoji` | `icon_custom_emoji_id` on buttons (bot owner needs Premium) |
| `notifications.custom_emoji_id_bird` | Custom emoji id for birds (@Stickers) |
| `notifications.custom_emoji_id_chipmunk` | Rodent / chipmunk emoji (Telegram) |
| `notifications.custom_emoji_id_open_live` | Open Live button |
| `notifications.paid_media_view_star_count` | Stars for photo view (0=free, 1–25000). `sendPaidMedia` |
| `notifications.paid_media_forward_star_count` | Free view: 0=allow forward, >0=block. Paid: forward allowed. |
| `general.notification_excluded_species` | Excluded species |
| `processor.save_images` | If true — save detection frames to disk for debugging. It does not control Telegram photo delivery |
| `processor.save_dataset_crops` | Default **false** (opt-in). If true — save `best_frame` to `data/dataset/train/<Species>/` |
| `processor.dataset_min_confidence` | Min confidence (0.0–1.0) for dataset crop. Default 0.5 |

**How BirdLense sends Telegram notifications:** first it tries to send an actual **photo** (`sendPhoto` / MTProto media) from `best_frame`; if that is unavailable, it falls back to a bbox crop from the video, then to a full frame. If Telegram rejects the media or the preview is broken, BirdLense falls back to a text message with link/button and records the fallback reason in observability (System → Observability).

**Telegram Bot API 9.4/9.5:** styled buttons, `<tg-time format="r">`, large previews (`link_preview_large`).

### If my.telegram.org shows ERROR (cannot create app / get keys)

**https://my.telegram.org** is run by Telegram; BirdLense cannot fix it. It often fails from some networks (VPN on/off, captcha, rate limits).

**Without api_id / api_hash:** do **not** use **MTProto** proxy type in Hub. Choose **SOCKS5 / HTTP** and set a proxy URL so your server can reach **`https://api.telegram.org` over HTTPS** (e.g. your own `socks5h://…`), or **no proxy** if Bot API is already reachable. **No api_id/api_hash needed** — bot token and `chat_id` are enough.

**MTProto** mode is only for traffic via an **MTProto proxy** (like the Telegram app). It uses Telethon and **requires** api_id+api_hash from my.telegram.org. If the site keeps failing, use SOCKS/HTTP (or direct) until you can obtain keys (other network, VPN, device, or help from someone who can open the site).

A practical public SOCKS5 source for quick testing: [ProxyGenerator](https://github.com/proxygenerator1/ProxyGenerator).

Proxy check example (expect `404`/`401` from Telegram API — this is normal and means the path to Telegram works):
`curl --proxy socks5h://IP:PORT --max-time 12 -s -o /dev/null -w "%{http_code}" https://api.telegram.org/botINVALID/getMe`

⚠️ Public proxies are unstable and unsafe for long-term production use; prefer your own SOCKS5/HTTPS proxy.

Auto-select best proxy on production server (one-shot):
`make refresh-telegram-proxy`

Scheduled auto-rotation (easy setup):
- Install server cron (default every 6 hours): `make proxy-rotation-install`
- Check status and recent logs: `make proxy-rotation-status`
- Remove schedule: `make proxy-rotation-remove`

The script `scripts/refresh-telegram-proxy.sh` tests proxies from the Hub host, picks the fastest working one, updates `notifications.telegram_proxy_type=socks_http` and `notifications.telegram_proxy_url`, makes a `user_config.yaml` backup, and restarts containers only when the selected proxy changes.

> Important: after updating repository scripts, run `make deploy` once, then install schedule.

### Custom emoji on buttons (Premium)

`use_custom_emoji` and id fields control button emoji:

| Mode | Behavior |
|------|----------|
| **Off** (default) | Unicode (🐦, 🐿️, 📺) — visible to everyone |
| **On** | `icon_custom_emoji_id` — **Telegram Premium required for bot owner** |

When on, configure:

- `custom_emoji_id_bird` — bird notifications  
- `custom_emoji_id_chipmunk` — rodents / small mammals (chipmunk emoji slot)  
- `custom_emoji_id_open_live` — Open Live  

If id missing — Unicode fallback.

**How to get custom emoji id:**

1. Send the emoji to [@RawDataBot](https://t.me/RawDataBot) — reply contains `custom_emoji_id`.
2. Or [@Stickers](https://t.me/Stickers) for pack ids.
3. Paste numeric id (example: `5368324170671202286`) into settings.

### Web Push

Browser push (addition or alternative to Telegram). Requires HTTPS (or localhost).

| Key | Description |
|-----|-------------|
| `web_push.enabled` | Auto-enabled on first UI subscription |
| `web_push.vapid_public_key` | Public VAPID (auto-generated) |
| `web_push.vapid_private_key` | Private VAPID (secret, masked in API) |

**Setup:** Settings → Notifications → Enable Web Push. Browser prompts; subscription stored server-side. Push to all subscribers on species detection.

**Requirements:** HTTPS (or localhost), `general.enable_notifications`, `notifications.base_url` for link in push. UI subscription now requires the same access as Settings (`settings_check_access()`), so a random LAN client cannot silently enable `web_push.enabled`.

## UI

| Key | Description | Where |
|-----|-------------|-------|
| `unknown_confidence_threshold` | Threshold (0–1) for “Unknowns” list. Default **0.48** | Settings → Processor → advanced block |

---

## Webhook

| Key | Description |
|-----|-------------|
| `url` | POST URL per detection. JSON: species, confidence, time, source. IFTTT, Zapier, scripts |

**Security limits:** only `http`/`https` URLs are allowed. Private / loopback / link-local targets (`127.0.0.1`, `192.168.x.x`, `10.x.x.x`, `localhost`, etc.) are blocked so the webhook cannot be abused as an SSRF bridge into your internal network.

**Trusted proxy:** if Gunicorn is behind a trusted reverse proxy and you want rate limiting to honor `X-Real-IP` / `X-Forwarded-For`, set `TRUSTED_PROXY=1` (see Environment variables table). Otherwise BirdLense uses only `remote_addr`.

---

## eBird

| Key | Description |
|-----|-------------|
| `ebird.country` | Country code (2 letters: US, RU, …) |
| `ebird.state` | Region (1–3 chars: NY, CA, MOS for Moscow Oblast) |
| `ebird.location_name` | Location name for checklist |
| `ebird.protocol` | Stationary \| Traveling \| Incidental \| Historical |
| `ebird.species_mapping` | eBird ↔ BirdLense for “Compare to region”. Example: `Gray-headed Woodpecker: Grey-headed Woodpecker` |
| `secrets.ebird_api_key` | eBird API for Overview “Compare to region”. Get key: [ebird.org/api/keygen](https://ebird.org/api/keygen) |

Settings → Advanced. Timeline “Export for eBird” does **not** need API key. Key is for “Compare to region”.

Semi-automatic mapping hints: Settings → Advanced, button next to `ebird.species_mapping` loads the regional eBird top and suggests lines (case / fuzzy); `GET /api/ui/settings/ebird-species-mapping-suggestions` (same access as settings). See [#136](https://github.com/Gfermoto/BirdLense-Hub/issues/136).

The species filter **Regional** uses the same regional species list (eBird top in your `ebird.*` region) **plus** any species with a **BirdNET MQTT** detection (`detection_provider` = `birdnet_mqtt` in stored detections). See [issue #132](https://github.com/Gfermoto/BirdLense-Hub/issues/132).

**Example Russia, Moscow Oblast:** `ebird.country=RU`, `ebird.state=MOS` (or `MO`). API region: `RU-MOS`.

---

## MCP

| Key | Description |
|-----|-------------|
| `enabled` | Enable MCP server |
| `token` | Access token (or `MCP_TOKEN` in env) |

---

## Prometheus / Grafana {#prometheus--grafana}

`GET /metrics` and `GET /api/metrics` — Prometheus format.

**Prometheus** — `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'birdlense'
    metrics_path: '/api/metrics'
    static_configs:
      - targets: ['birdlense:8085']  # or YOUR_HOST:port
    scrape_interval: 15s
```

**Metrics:** CPU, memory, disk, GPU (if present), `birdlense_detections_total`, `birdlense_species_count`, `birdlense_videos_total`.

**Optional (hub exposed beyond a trusted LAN):** set **`BIRDLENSE_METRICS_TOKEN`** to a non-empty secret — then `GET /metrics`, `GET /api/metrics`, and `GET /api/metrics/summary` return **401** unless the request includes `Authorization: Bearer <same token>`. Configure your Prometheus scrape job with `authorization` / bearer credentials per Prometheus docs.

**Grafana** — Prometheus datasource, dashboard from metrics.

### System page metrics history {#system-page-metrics-history}

Separate from Prometheus: SQLite table `system_resource_sample`, background sampler stores CPU/RAM/disk/GPU snapshots. The UI calls `GET /api/ui/system/metrics/history`.

| Environment variable | Default | Range | Purpose |
|---------------------|---------|-------|---------|
| `BIRDLENSE_SYSTEM_METRICS_INTERVAL_SEC` | `30` | 10–600 | Seconds between samples |
| `BIRDLENSE_SYSTEM_METRICS_RETENTION_HOURS` | `72` | 6–720 | Drop rows older than this (hours) |
| `DISABLE_SYSTEM_METRICS_SAMPLER` | — | `1` / `true` | Disable sampler (tests, debugging) |

### Alerting (Prometheus + Alertmanager)

Ready-made examples live in the repo (tune thresholds and job labels to match your scrape config):

| File | Purpose |
|------|---------|
| [`examples/prometheus/birdlense.rules.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/examples/prometheus/birdlense.rules.yml) | Alerts: target down, disk/memory/CPU pressure, optional “no new detections in 24h” |
| [`examples/prometheus/alertmanager.birdlense.example.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/examples/prometheus/alertmanager.birdlense.example.yml) | Minimal Alertmanager `route` / `receivers` skeleton |

**Prometheus** — add `rule_files` next to `scrape_configs`:

```yaml
rule_files:
  - 'birdlense.rules.yml'   # path to the copied example
```

**Notes:**

- Default rules assume scrape **`job_name: birdlense`** (see `up{job="birdlense"}`). If you rename the job, update every `job=` matcher in the rule file.
- **`BirdlenseDetectionsUnchanged24h`** is optional and noisy when the feeder is off-season — increase `for`, mute in Alertmanager, or remove the rule group `birdlense-optional-activity`.
- GPU alerts are not included: `birdlense_gpu_usage_percent` is only exported when the container sees a usable GPU sysfs path; “stall” is better diagnosed via **System → Processor logs** and `/api/ui/status`.

Tracked as [issue #57](https://github.com/Gfermoto/BirdLense-Hub/issues/57).

---

## Secrets

Coordinates and API keys. Settings → Advanced. Prefer env for keys: `OPENWEATHER_API_KEY`.

| Key | Description |
|-----|-------------|
| `openweather_api_key` | OpenWeather for weather widget |
| `xeno_canto_api_key` | Xeno-canto for bird songs (xeno-canto.org/account) |
| `ebird_api_key` | eBird “Compare to region” |
| `latitude`, `longitude` | Weather and eBird |

**Operational rotation** (backup, restart, verification, rollback): [SECRETS_ROTATION.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/SECRETS_ROTATION.md).

---

## Bird food (default catalog)

The app ships a **curated default list** of feeder foods (US + EU-oriented names and hints). **Source of truth in code:** [`app/web/seed/seed.py`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/seed/seed.py) → `seed_bird_food()`. Image paths point at `data/images/food/*` in the app bundle.

**Existing databases:** on each startup, `seed()` **merges** any catalog entries **missing by `name`** — upgrades pick up new defaults without duplicating rows. The legacy catalog row **Apple pieces** is **removed** on startup (see `seed.py`), including clearing `video_bird_food_association` links. Operators can still add custom foods via **`GET` / `POST /api/ui/birdfood`** (see [API.md](../contributor/api.md)).

Tracked as [issue #134](https://github.com/Gfermoto/BirdLense-Hub/issues/134).

---

## See also

[INSTALL](./install.md) · [ARCHITECTURE](../contributor/architecture.md) · [ACCESS_CONTROL](../contributor/access-control.md) · [API](../contributor/api.md) · [SCENARIOS](./scenarios.md) · [GLOSSARY](./glossary.md) · [SECRETS_ROTATION](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/SECRETS_ROTATION.md) · [PUBLIC_RELEASE_CHECKLIST](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/PUBLIC_RELEASE_CHECKLIST.md)
