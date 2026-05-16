# Testing BirdLense Hub

[Русский](./TESTING.ru.md)

---

> **Security:** If your settings password was exposed in logs or chat, change it under **Settings → General**.
>
> **Placeholders:** `YOUR_HOST` — hostname or IP; `YOUR_SSH_HOST` — host alias from `~/.ssh/config`; `YOUR_REMOTE_DIR` — app root on the server (**default deploy:** `/root/BirdLense`, see `DEPLOY_REMOTE_DIR`); `/opt/birdlense` in older docs is a legacy example.

---

## 1. Automated tests (development & CI)

On **GitHub** (PR/push to `main` and `dev`), workflow **[`.github/workflows/ci-pr.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/ci-pr.yml)** (**CI**) runs these jobs in parallel:

| Job | What it does |
|-----|----------------|
| **`python-security`** | **Bandit** on `web/` + `processor/src`; **pip-audit** on `web/requirements.txt` + `processor/requirements.txt` |
| **`openapi-contract`** | **Ruff** — `ruff check` + `ruff format --check` on `web/` + `processor/src/`; **radon cc** summary; **`scripts/check-docs-version.py`**; multiple **pytest** slices (OpenAPI contract, species registry, dataset export, util metadata, bird food seed, Xeno-canto, settings mutations, processor videos, system routes) |
| **`ui-build`** | **Node 22** — `npm ci`; **`npm run codegen:openapi`** + drift check on `src/generated/openapi-types.ts`; **Vitest** (`npm run test -- --run`); **`npm run coverage`** + **`npm run coverage:critical`**; **`npm run typecheck`**; `npm run lint`; production build of the SPA (`app/ui`) |
| **`docs`** | **Python 3.12** — `check-docs-version.py`, **Settings UI coverage** report (artifact + summary), **MkDocs** `build --strict` |
| **`docker-tests`** | Docker **Buildx** — fetch processor weights, `docker compose build birdlense`, **`make test`** + **`make test-web`**, **Playwright** `smoke.spec.ts` against compose, **`make verify-strict-quality BASE_URL=...`**, **catalog cards audit** script (artifact) |

The same **`ci-pr.yml`** file is also triggered on a **daily cron** (repository **default branch** only, in GitHub) and via **`workflow_dispatch`**, running the same jobs without a code push.

**`docker-tests`** is the usual **required** check in the **Protect** ruleset on `main` (see [GITHUB_SETUP_GH](./GITHUB_SETUP_GH.md)). Other jobs should stay green before merge.

**Policy & thresholds:** [CI_AND_QUALITY](./CI_AND_QUALITY.md) (pip-audit ignores, Ruff format, npm audit, OpenAPI→TypeScript codegen).

**Related workflows:** **CodeQL** (see [CODEQL](./CODEQL.md)); **E2E (Playwright)** scheduled / manual — [§ E2E](#e2e-playwright) below. **npm audit (UI)** — weekly + `workflow_dispatch`: [`.github/workflows/npm-audit-scheduled.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/npm-audit-scheduled.yml) runs `npm audit --omit=dev --audit-level=moderate` in `app/ui` (not a required PR check; policy in workflow comments — [#284](https://github.com/Gfermoto/BirdLense-Hub/issues/284)).

### Test pyramid & targeted local runs ([#348](https://github.com/Gfermoto/BirdLense-Hub/issues/348))

**Source of truth for “what CI runs”:** [`.github/workflows/ci-pr.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/.github/workflows/ci-pr.yml) (parallel jobs) and, for a single local driver, **`scripts/ci-full-local.sh`** (`make ci-local` / `make ci-local-docker`).

| Layer / gate | Where it runs | Main regression classes caught |
| -------------- | ---------------- | -------------------------------- |
| **Bandit + pip-audit** | CI `python-security`; start of `ci-full-local.sh` | insecure patterns; known vulnerable deps |
| **Ruff + pytest slices** | CI `openapi-contract`; `ci-full-local.sh` (full `pytest web/tests/` in `.venv-ci`) | style/format; API/OpenAPI drift; registry, dataset export, settings/auth, processor ingest smoke |
| **UI (Node)** | CI `ui-build`; `ci-full-local.sh` | TS/React correctness, Vitest, ESLint, production build, OpenAPI → TS codegen drift |
| **Docs** | CI `docs`; `ci-full-local.sh` | MkDocs strict, settings UI coverage script, `VERSION` sync |
| **Docker + processor + web + E2E** | CI `docker-tests`; tail of `ci-full-local.sh` | image build, processor + Flask in container, Playwright smoke, catalog audit |

**Fast paths (typical change → run this first, often &lt; 5–10 minutes on a warm machine):**

| You changed… | Suggested check |
| -------------- | ----------------- |
| OpenAPI / generated TS types only | `cd app/ui && npm run codegen:openapi` then `git diff --exit-code -- src/generated/openapi-types.ts`; or **`make test-web-contract-local`** from repo root (OpenAPI contract + strict UI API auth tests in `app/.venv`) |
| Flask route / service (web only) | `cd app && make test-web-local` after `make venv-web`, or narrow: `pytest web/tests/test_<area>.py` |
| Processor logic (no heavy YOLO) | `cd app && make test-processor-light` |
| Markdown / MkDocs only | `.venv-docs/bin/mkdocs build --strict` from repo root |
| “Full parity before push” | `make ci-local` + **`make ci-local-docker`** |

**E2E selector policy:** Prefer stable **`data-testid`** on elements that drive smoke flows (nav pills, empty states, **Settings password gate** / overlays where `aria-hidden` can confuse role-based queries). New Playwright specs should default to `getByTestId` for those widgets; use text/role selectors only when they are unambiguous in both themes and locales.

### Processor unit tests

```bash
cd app && make test
```

Runs processor `unittest` inside Docker (detection strategy, decision logic). Requires ultralytics; **production path is two_stage** (binary `.pt` + classifier `.pt`; CI runs `scripts/fetch-processor-weights.sh` for the active pair, and `--legacy-single-stage` is only for the compatibility `app/yolo11n.pt`; locally run the same before `make test` if paths are empty).

> **Memory / RAM:** Processor tests load YOLO inside the container and can use **several GB of RAM**. On a **small VPS or laptop** with tight limits, `make test` (or the **`docker-tests`** CI job) may exit with **SIGKILL / exit 137** (OOM). Prefer a machine with **≥8 GB** free for Docker, close other heavy apps, or run tests on **GitHub Actions** instead of locally.

**Lighter processor run (#282):** `cd app && make test-processor-light` sets `SKIP_HEAVY_PROCESSOR_TESTS=1` and runs `pytest processor/tests/ -m "not heavy"`. That skips the **TwoStageStrategy** integration tests that load real `.pt` weights (same skip if you export the env var yourself). Pytest tests can be marked with `@pytest.mark.heavy` to opt into the same skip. **CI** still runs the full `make test` by default.

### Web API tests

```bash
cd app && make test-web
```

Runs pytest against the Flask API (health, status, settings, feed, cameras). Build the image first: `make build`.

Includes **`TestVerifyPasswordRateLimit`** — `POST /api/ui/settings/verify-password` returns **429** after five wrong passwords in 60s, **`Retry-After`**, separate buckets per `X-Real-IP`, counter reset on success ([ACCESS_CONTROL](./ACCESS_CONTROL.md)).

### Domain integrity quality gate

Admin snapshot:

```bash
curl -s http://YOUR_HOST:8085/api/ui/system/domain-health
```

At minimum, check:

- `orphaned_visits = 0`
- `visit_species_mismatches = 0`
- `duplicate_name_group_count` does not drift upward without a known migration/import
- `duplicate_clip_candidates_24h` is not turning into a repeated pattern
- review-only rows remain explainable and do not leak into visits or monthly stats

Contract details: [DOMAIN_CONTRACT](./DOMAIN_CONTRACT.md).

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

**Suites:** `smoke.spec.ts` (home, nav, Settings, Live, **System** readiness strip), `api.spec.ts` (health, status, settings, cameras, weather, feed dispense, **`GET /api/ui/system/config-audit`**), `settings.spec.ts` (form, Video/MQTT/Feed sections, **Processor → save max recording seconds** round-trip when admin + optional `E2E_SETTINGS_PASSWORD`), `migration.spec.ts` (Migration **From year** filter + reset to **All years**; **skipped** if the calendar has no species table / empty DB).

API-only (no browser): `cd app/e2e && npm test -- --grep @api`

Debug one file / UI mode: `cd app/e2e && npx playwright test tests/migration.spec.ts` or `npx playwright test --debug tests/migration.spec.ts`.

**Scheduled CI:** workflow **E2E (Playwright)** (`.github/workflows/e2e-scheduled.yml`) runs **daily** and on **`workflow_dispatch`** — not a required check on every PR.

**Local parity:** from repo root, run **`make ci-local`** and **`make ci-local-docker`** to mirror the required CI layers without opening a PR — see [CI_AND_QUALITY](./CI_AND_QUALITY.md).

> `make ci-local-docker` runs local `verify-strict-quality` as a probe; set `CI_STRICT_QUALITY_REQUIRED=1` to make it blocking (close to CI gate behavior).

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
BASE_URL=http://YOUR_HOST:8085 make verify
curl -s http://YOUR_HOST:8085/api/ui/health
curl -s http://YOUR_HOST:8085/api/ui/readiness
curl -s http://YOUR_HOST:8085/api/ui/status
```

Expect:

- `health` → `{"status":"ok"}`
- `readiness` → `"ready": true`
- `status` → `processor: ok|offline`, `web: ok`

Motion source: `opencv` or `frigate` as configured.

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

1. `BASE_URL=http://YOUR_HOST:8085 make verify` → PASS
2. `curl .../api/ui/status` → `processor: ok`; if Frigate motion, `mqtt: ok`
3. `.env` has real `PROCESSOR_SECRET`; deploy health URL is the **server**, not localhost
4. Last 50 lines of processor log — no errors / 403
5. `./scripts/test-deploy-recognition.sh` → new clip in UI (YOLO path)
6. If Frigate: synthetic `mosquitto_pub` → `Frigate trigger` in log

### 2.5 Telegram: detections missing until restart

Startup message **“App is UP!”** is from the **web** app. **Detection** notifications are sent by the **processor** via `POST /api/processor/notify/detections`. If that returns 403, you get no bird alerts.

1. **Settings → Notifications → Test Telegram** — if OK, tokens are fine; look at processor ↔ API.
2. Processor log: `Notify species failed 403` → fix `PROCESSOR_SECRET`.
3. Confirm detections exist: log line `Processing stopped. Video Result: [...]` with species; empty result → no Telegram by design.
4. Check `general.notification_excluded_species`.

## See also

[INSTALL](./INSTALL.md) · [CONFIGURATION](./CONFIGURATION.md) · [TROUBLESHOOTING](./TROUBLESHOOTING.md)
