# Testing BirdLense Hub

[Русский](./TESTING.ru.md)

---

> **Security:** If your settings password was exposed in logs or chat, change it under **Settings → General**.
>
> **Placeholders:** `YOUR_HOST` — hostname or IP; `YOUR_SSH_HOST` — host alias from `~/.ssh/config`; `YOUR_REMOTE_DIR` — app root on the server (e.g. `/opt/birdlense`).

---

## 1. Automated tests (development & CI)

On **GitHub** (PR/push to `main` and `dev`), workflow **CI** runs:

- **`ui-build`** — `npm ci` + production build of the SPA  
- **`docs`** — MkDocs `--strict` + docs version check  
- **`docker-tests`** — `docker compose build` + `make test` + `make test-web` (same as below)

**`docker-tests`** is a **required** check in the **Protect** ruleset on `main` (see [GITHUB_SETUP_GH](./GITHUB_SETUP_GH.md)).

### Processor unit tests

```bash
cd app && make test
```

Runs processor `unittest` inside Docker (detection strategy, decision logic). Requires ultralytics/ncnn in the image.

> **Memory / RAM:** Processor tests load YOLO/NCNN inside the container and can use **several GB of RAM**. On a **small VPS or laptop** with tight limits, `make test` (or the **`docker-tests`** CI job) may exit with **SIGKILL / exit 137** (OOM). Prefer a machine with **≥8 GB** free for Docker, close other heavy apps, or run tests on **GitHub Actions** instead of locally.

### Web API tests

```bash
cd app && make test-web
```

Runs pytest against the Flask API (health, status, settings, feed, cameras). Build the image first: `make build`.

Includes **`TestVerifyPasswordRateLimit`** — `POST /api/ui/settings/verify-password` returns **429** after five wrong passwords in 60s, **`Retry-After`**, separate buckets per `X-Real-IP`, counter reset on success ([ACCESS_CONTROL](./ACCESS_CONTROL.md)).

### Coverage

```bash
cd app && make test-coverage   # console report
cd app && make test-report     # + HTML → app/htmlcov/index.html
```

Config: `app/.coveragerc` (excludes tests, `app_config`, scripts). Good next targets for coverage: `ui_system_routes`, `retention_service`, `visit_processor`, `processor_routes`.

### E2E (Playwright)

E2E runs against a **live** instance (UI + API).

1. Start the stack: `cd app && make start`
2. Run: `cd app && make test-e2e`
3. Remote: `cd app && BASE_URL=http://YOUR_HOST:8085 make test-e2e`
4. **Settings password:** set `E2E_SETTINGS_PASSWORD=...` for a full run. Without it, Settings tests and `GET /api/ui/settings` are **skipped**.

**Suites:** `smoke.spec.ts` (home, nav, Settings, Live), `api.spec.ts` (health, status, settings, cameras, weather, feed dispense), `settings.spec.ts` (form, Video/MQTT/Feed sections), `migration.spec.ts` (Migration **From year** filter + reset to **All years**; **skipped** if the calendar has no species table / empty DB).

API-only (no browser): `cd app/e2e && npm test -- --grep @api`

Debug one file / UI mode: `cd app/e2e && npx playwright test tests/migration.spec.ts` or `npx playwright test --debug tests/migration.spec.ts`.

**Scheduled CI:** workflow **E2E (Playwright)** (`.github/workflows/e2e-scheduled.yml`) runs **weekly** and on **workflow_dispatch** — not a required check; use it to catch regressions without running Playwright on every PR.

**Expanding coverage:** extra journeys (full login, timeline drill-down, species correction flows) are added **incrementally** when a change needs them; track new specs in the PR and in this doc — no standing umbrella issue required.

### MQTT & ESPHome in `/api/ui/status`

The status payload includes:

- `mqtt`: `ok` | `error` | `not_configured` | `not_used`
- `esphome`: `ok` | `error` | `not_configured` | `not_used`

When `feed.source` is `mqtt`, the broker is checked; when `esphome`, the feeder URL is checked. Indicators appear in the nav (**StatusIndicator**).

---

## 2. Post-deployment verification

Use this when you need confidence **without** waiting for real birds (e.g. after a night deploy).

> **Common pitfall:** processor → API calls failing with **403** if `PROCESSOR_SECRET` in `.env` is wrong or still a literal `${PROCESSOR_SECRET}`. Fix deploy scripts and re-check (see below).

### 2.1 Health & logs (first pass)

```bash
curl -s http://YOUR_HOST:8085/api/ui/health
curl -s http://YOUR_HOST:8085/api/ui/status
```

Expect `processor: ok`, `web: ok`. Motion source: `opencv` or `frigate` as configured.

**Processor logs:** UI **System → Processor logs**, or:

```bash
ssh YOUR_SSH_HOST "tail -100 YOUR_REMOTE_DIR/app/data/processor.log"
```

Check: models loaded (NCNN/YOLO), motion source line, no `403`, `Connection refused`, or Python tracebacks.

**403 / `PROCESSOR_SECRET`:** On the server, `grep PROCESSOR_SECRET YOUR_REMOTE_DIR/app/.env` must show a **32-char hex** value, not `${PROCESSOR_SECRET}`.

**Gray status icons:** If Video/MQTT/YOLO stay gray while things work, heartbeat may be failing:

`/api/ui/status/debug` now requires an authenticated admin settings session. Check it from a browser after admin login and Settings unlock, or pass the session cookie explicitly in your HTTP client.

Interpret: `last_heartbeat: null`, stale `updated_at`, `processor_secret_configured: false`, or repeated `403` heartbeat errors in processor logs → fix secret alignment between processor and web.

### 2.2 Full pipeline smoke (YOLO path)

Script (uses latest `video.mp4` under `data/recordings/` or `VIDEO_ID` from API):

```bash
./scripts/test-deploy-recognition.sh
VIDEO_ID=37 ./scripts/test-deploy-recognition.sh
```

Uses `--fake-motion true` and a separate MQTT client id so it does not fight the main processor. **Scope:** processor + YOLO + API — **not** Frigate recording trigger, BirdNET, or Go2RTC connectivity.

### 2.3 MQTT (Frigate / BirdNET)

Watch `processor.log` for:

| Signal | Log hint |
|--------|----------|
| Connected | `MQTT aggregator connected` |
| Frigate triggered | `Frigate trigger: camera=... -> recording` |
| Skipped | `Frigate event skipped (no trigger): ...` |
| Fallback | `Frigate MQTT not connected, falling back to OpenCV` |

**Synthetic Frigate event** (adjust broker, camera id, topic prefix to match your config):

```bash
mosquitto_pub -h BROKER -p 1883 -t "frigate/events" \
  -m '{"after":{"camera":"birdbox","label":"bird","sub_label":"Bird","top_score":0.95,"frame_time":'$(date +%s)'}}'
```

**Synthetic BirdNET** (merge path; does not start recording alone):

```bash
mosquitto_pub -h BROKER -p 1883 -t "birdnet" \
  -m '{"Common_Name":"Northern Cardinal","Confidence_Score":0.85}'
```

Use `-u` / `-P` if the broker requires auth.

### 2.4 Overnight checklist (minimal)

1. `curl .../api/ui/status` → `processor: ok`; if Frigate motion, `mqtt: ok`
2. `.env` has real `PROCESSOR_SECRET`; deploy health URL is the **server**, not localhost
3. Last 50 lines of processor log — no errors / 403
4. `./scripts/test-deploy-recognition.sh` → new clip in UI (YOLO path)
5. If Frigate: synthetic `mosquitto_pub` → `Frigate trigger` in log

### 2.5 Telegram: detections missing until restart

Startup message **“App is UP!”** is from the **web** app. **Detection** notifications are sent by the **processor** via `POST /api/processor/notify/detections`. If that returns 403, you get no bird alerts.

1. **Settings → Notifications → Test Telegram** — if OK, tokens are fine; look at processor ↔ API.
2. Processor log: `Notify species failed 403` → fix `PROCESSOR_SECRET`.
3. Confirm detections exist: log line `Processing stopped. Video Result: [...]` with species; empty result → no Telegram by design.
4. Check `general.notification_excluded_species`.

### 2.6 Gallery (opt-in public upload)

1. **Local smoke:** from repo root, `docker compose -f docker/gallery-test/docker-compose.yml up -d` → receiver at `http://localhost:8086/api/upload` (see [CONFIGURATION](./CONFIGURATION.md) → Gallery).
2. **BirdLense + test gallery on one Docker network:** `cd app && docker compose -f docker-compose.yml -f docker-compose.gallery-test.yml up -d`, then set **Settings → Gallery** `upload_url` to `http://gallery-test:5000/api/upload` (service name, not host `localhost`).
3. **Trigger:** process a clip with **video** YOLO detections that include **track frames**; after `POST /api/processor/videos`, the web app uploads in a background thread. Logs: `Gallery upload:` or `Gallery upload failed` / `Gallery upload thread failed`.
4. **pytest:** `TestGalleryUploadThread` and `TestGalleryUploadService` in `app/web/tests/test_gallery_upload.py` (run via `make test-web`).

---

## See also

[INSTALL](./INSTALL.md) · [CONFIGURATION](./CONFIGURATION.md) · [TROUBLESHOOTING](./TROUBLESHOOTING.md)
