# Roadmap — BirdLense Hub

Direction of travel and current stack. **Shipped items** are summarized here; details live in [Changelog](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) and [FEATURES](../user/features.md).

> **SOTA Reality Status (2026-06-05):** wave-controls (#528–#554) закрыты. Customer acceptance **blocked** on CV pipeline (#606) and storage integrity (#601). Primary plans: `CONSORTIUM_ARCHITECTURE_PLAN_2026-06.md`, `CV_PIPELINE_RECOVERY_PLAN_2026-06.md`.

[Русский](../contributor/roadmap.md)

---

## Current stack (April 2026)

| Component | Version / note |
|-----------|----------------|
| **Ultralytics** | **8.4.33** at runtime (`app/processor/requirements.txt`, installed via pip in the image). Base image remains **`ultralytics/ultralytics:8.4.21`** (newer base tags broke ngx_brotli build against nginx in CI; see [CHANGELOG](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) **0.3.1**). |
| **Platform** | **x86/amd64** (Intel NUC — default). **aarch64:** experimental profile `jetson_nano` (Jetson Nano B01 4GB) — [#645](https://github.com/Gfermoto/BirdLense-Hub/issues/645); not generic ARM/Apple Silicon |
| **Detection** | `two_stage`: binary `.pt` + YOLO11n-cls (EU); `single_stage` fallback if weights missing |
| **EU classifier** | **Birder eu-common 707** (`birder_eu`, #516) — `convnext_v2_tiny_eu-common256px`; legacy YOLO `best.pt` opt-in |
| **US classifier** | `best_US.pt` — NABirds (fallback) |
| **React** | **19.x** (`^19.0.0` in `app/ui/package.json`; resolved lock may pin a patch) |
| **Vite** | **6.x** (`^6.4.2` in `app/ui/package.json`) |
| **Web DB schema** | **Flask-Migrate / Alembic** — revisions under `app/web/migrations/`; `create_app()` runs `db.create_all()` then `upgrade()` (see [CHANGELOG on GitHub](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) *[Unreleased]* / issue [#225](https://github.com/Gfermoto/BirdLense-Hub/issues/225); local stub: [project/changelog](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md)) |

---

## In progress (June 2026)

### Primary execution tracks

| Track | Epic | Focus |
|-------|------|--------|
| **Storage / NVR parity** | [#601](https://github.com/Gfermoto/BirdLense-Hub/issues/601) | FinalizeTransaction, QuotaMaintainer, ReconcileJob, honest readiness [#605](https://github.com/Gfermoto/BirdLense-Hub/issues/605) |
| **CV pipeline recovery** | [#606](https://github.com/Gfermoto/BirdLense-Hub/issues/606) | Tracks, false bbox, species — `docs/strategy/CV_PIPELINE_RECOVERY_PLAN_2026-06.md` |
| **Jetson Nano edge** | [#645](https://github.com/Gfermoto/BirdLense-Hub/issues/645) | DeepStream/TRT/NVDEC, гибрид «сторож + охотник» — [runbook 21 шаг](../strategy/jetson-nano-edge-setup-and-migration.md) |

**Jetson sub-issues (E0–E14):** [#646](https://github.com/Gfermoto/BirdLense-Hub/issues/646)–[#660](https://github.com/Gfermoto/BirdLense-Hub/issues/660). Runbook: шаги 1–8 provisioning, 9–15 stack/TRT/benchmark gate, 17–18 камеры/RTSP, 19–21 deploy/smoke/recovery.

**Field symptoms (Jun 2026):** no tracks, false/sticky bboxes, classifier stuck on Bird → #607–#611.

**Superseded as primary plan:** closed [#517](https://github.com/Gfermoto/BirdLense-Hub/issues/517), [#555–#557](https://github.com/Gfermoto/BirdLense-Hub/issues/555) (residual work split into #601 + #606).

---

## In progress (May 2026 — live tracking / overlay) — historical

### Acceptance-critical (superseded 2026-06)

- ~~**Primary epic:** [#517](https://github.com/Gfermoto/BirdLense-Hub/issues/517)~~ → #601 + #606
- ~~**Release blockers (P0):** [#555](https://github.com/Gfermoto/BirdLense-Hub/issues/555), [#556](https://github.com/Gfermoto/BirdLense-Hub/issues/556), [#557](https://github.com/Gfermoto/BirdLense-Hub/issues/557)~~ — closed; CV gaps → #606

- **Sticky bbox / phantom tracks** — `track_geometry` (sparse 3-frame rule), strip `review_only` overlay frames before persist, VPS `tracker_remember_seconds: 3.5` (was 8 in `user_config`). Aligns with [SOTA Wave 3](../strategy/SOTA_WAVE3_ROADMAP_2026.md) P0 hard-negatives / threshold contract.
- **Species vocabulary (#506)** — `services/species_catalog/vocabulary.py`: classifier labels + arbitration. Catalog `scope=project` (default); `scope=allowlist` = активный классификатор (Birder 707 / EfficientNet 525). Ingest не сбрасывает уже наблюдаемые виды в Unknown.
- **Next:** track regen on affected clips; golden-set gate (`recording_session_summary.yolo_frames_with_tracks`).

## Recently delivered (high level)

- **Home Assistant** — MQTT discovery (e.g. last species, bird-detected). See [CONFIGURATION](../user/configuration.md) → MQTT.
- **Dataset pipeline** — `best_frame` in YOLO layout, ZIP export (`GET /api/ui/dataset/export`), relabel moves on-disk crops. **System → Storage**.
- **Video prev/next (same UTC day)** — [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) closed (**v0.2.6**): `GET /api/ui/videos/:id/neighbors` + arrows on video details (browse clips for that calendar day in UTC without losing list context).
- **Overview mean recording duration** — [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) closed: metric is the average length of **one clip** (`Video`), not a visit aggregate; PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106).
- **System: resource charts with server-side history** — SQLite `system_resource_sample`, `GET /api/ui/system/metrics/history`, UI windows 6/24/48 h plus live tail; tune with `BIRDLENSE_SYSTEM_METRICS_*` — [CONFIGURATION](../user/configuration.md) → Prometheus / Grafana.

---

## Backlog consilium (April 2026)

**Brainstorm roles:** product (operator value), security, platform/infra, ML & data, integrations (MQTT/HA/Frigate), UX, docs & OSS hygiene.

**Outcome:** triaged items are **GitHub Issues** (not shipped until closed in a release): [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57), [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) (operator UX — Apr 2026; phase B: Unknowns snackbar **Open video**). **Done:** [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) (git-history secret scan + SECURITY updates), [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) (`export_birdlense_to_yolo.py`), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) (MQTT reconnect backoff + missed-events docs clarity), [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) (SQLite backup/restore in System UI + INSTALL/TROUBLESHOOTING updates), [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) (locale switch + third locale `zh`, Simplified Chinese), [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) (scheduled smoke for published `ghcr` image), [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) (OpenAPI contract smoke in CI + local run command), [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) (gallery upload thread app context, v0.2.4), [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) (same-UTC-day video prev/next, v0.2.6), [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) (local TZ / cross-day / docs), [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) (Overview: mean duration = **per-`Video`** average, not visit span). [#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) (generic ARM Docker) **closed** — целевой edge-профиль: `jetson_nano` ([#645](https://github.com/Gfermoto/BirdLense-Hub/issues/645)), не произвольный aarch64.

**Put them on the Project board:** OAuth scopes often loop on device login — use a **classic PAT** (`repo` + `project`) in `GH_TOKEN` or `scripts/.env.project` (see `scripts/env.project.example`), then:

```bash
bash scripts/github-project-add-backlog-consilium.sh
```

All open issues/PRs: `bash scripts/github-project-import-open-items.sh`. Or add cards manually in the GitHub UI.
Status/assignee/checklist sync: `bash scripts/github-project-sync.sh --assign Gfermoto`.

| # | Theme | Issue | Labels (summary) |
|---|--------|-------|------------------|
| 1 | Rate limiting for settings / auth API | [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46) ✅ `verify-password`, docs, tests | `area:web`, P2 |
| 2 | Git history secret scan (maintainer) | [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) ✅ gitleaks script + SECURITY EN/RU | `area:infra`, P3, `documentation` |
| 3 | `export_birdlense_to_yolo.py` training export | [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) ✅ YOLO cls `train/val` export script | `area:processor`, P2 |
| 4 | MQTT reconnect / missed-events clarity | [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) ✅ reconnect backoff + docs | `area:processor`, P2 |
| 5 | UI: backup / restore SQLite | [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) ✅ System backup/restore + docs | `area:web`, P3 |
| 6 | UI i18n framework | [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) ✅ locale switch + `zh` (Simplified Chinese) | `area:web`, P3 |
| 7 | CI: scheduled image smoke test | [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) ✅ workflow `Docker image smoke (published)` (`ghcr ... :latest` + `/api/ui/health`) | `area:infra`, P3 |
| 8 | CI: OpenAPI contract tests | [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) ✅ `openapi-contract` in CI + `web/tests/test_openapi_contract.py` | `area:web`, P3 |
| 9 | Yearly species checklist / life list | [#55](https://github.com/Gfermoto/BirdLense-Hub/issues/55) ✅ Migration page: year filter + table (rows and Σ) — no duplicate checklist block | `area:web`, P3 |
| 10 | CORS demo host → config/env | [#56](https://github.com/Gfermoto/BirdLense-Hub/issues/56) ✅ demo host moved out of hardcoded CORS defaults into `CORS_DEFAULT_ORIGINS` / `CORS_ORIGINS` | `area:web`, P3 |
| 11 | Docs: Prometheus alert examples | [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) ✅ `examples/prometheus/`, [CONFIGURATION](../user/configuration.md) | `area:docs`, P3 |
| 12 | Gallery upload threading / app context | [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) ✅ app context in upload thread + docs/tests **v0.2.4** | `area:web`, P2, `bug` |
| 13 | Manual species correction: unify Unknowns vs in-video flow | [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) ✅ phases A+B+C: shared API + Unknowns **Open video** snackbar + recent shared correction history — [UX spec](../../archive/internal/docs-legacy/UX_UNKNOWN_VIDEO_CORRECTION.md) | `area:web`, P2 |
| 14 | Video navigation: sequential browse (e.g. same day), no list reset | [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) ✅ UI + `GET /videos/:id/neighbors` **v0.2.6** | `area:web`, P2 |
| 15 | Video neighbors: local TZ, cross-day jump, docs clarity (follow-up to #82) | [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) ✅ local day + `cross_day` + API/UI docs | `area:web`, P3 |
| 16 | Overview: “mean duration” used visit span instead of per-recording average | [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) ✅ mean over `Video` rows (PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106)); RU/EN labels | `area:web`, P3, `bug` |
| 17 | Detection: false positives and inanimate objects — strategy (two_stage vs single_stage+COCO, thresholds, weights) | Consilium: [§ below](#detection-strategy-consilium) · ties to [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) | P2, processor, ML |

<h3 id="detection-strategy-consilium">Detection strategy consilium</h3>

**Goal:** run a consilium (product/operator, ML, platform) and record a decision on reducing **false positives** and **non-living object** detections in production. By default this runs **after** the current development wave is closed and basic manual acceptance; see [§ Finish work, then operator testing](#completion-then-operator-testing).

**Context:** with `detection_strategy: two_stage` and values in `user_config.yaml`, behavior **does not** match **single_stage** + typical COCO defaults (animals-only vs full COCO classes). Deploying code does not overwrite `user_config.yaml`.

**Options to compare (combinations allowed):**

- keep **two_stage** and tune **`min_confidence_binary`** / **`min_confidence_to_process`**, and/or retrain/replace the binary detector;
- move to **single_stage** + COCO (or another detect model) and rely on the animal filter / custom classes;
- factor in Frigate / extra motion triggers.

See [CONFIGURATION.md](../user/configuration.md) (processor, motion). Non-bird classes overlap [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) — consilium should decide one epic vs child issues.

**Do not forget (checklist):**

| Step | Action |
|------|--------|
| 1 | Capture the live hub **`processor`** snippet from `user_config.yaml`: `detection_strategy`, `models.binary` / `models.classifier`, `min_confidence_binary`, `min_confidence_to_process`, `detector_scope`. |
| 2 | Note **symptoms**: what triggers false positives / non-animal detections (scene, time of day, weather when possible). |
| 3 | At the consilium, pick an approach (two_stage + thresholds/model **or** single_stage + COCO/custom **or** Frigate hybrid, etc.) and **write the decision** into Issue(s) (one epic or children). |
| 4 | After the decision: update **this ROADMAP** (row 17 — outcome or link to closed issue), **CONFIGURATION** / examples if keys change; on the server **edit `user_config.yaml` manually** if needed (**deploy does not overwrite it**). |
| 5 | Keep in sync with [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) by explicit choice: one workstream or separate cross-linked issues. |

### Triage: Issue vs. Discussion

| Use | When |
|-----|------|
| **[GitHub Issue](https://github.com/Gfermoto/BirdLense-Hub/issues)** | Clear scope, definition of done, fits an area label (`area:*`) and priority — work can land on the **Project** board. |
| **[Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** | Exploratory ideas, multiple design options, “should we at all?”, community input before committing. |

**After consilium:** new tracked work → create/update the Issue, add the card to the Project (`github-project-add-backlog-consilium.sh` or manually), then **update this ROADMAP** table in the same PR or follow-up.

**Reporting (all shipped work, not only consilium):** every shipped item has a **GitHub Issue** (open one if missing) and, when tracked, a card on **BirdLense Hub — Roadmap**. When done: comment (outcome + PR links), **close** the issue, set board **Status → Done** (with a PAT: `bash scripts/github-project-mark-done.sh <n>`). For routine hygiene, run `bash scripts/github-project-sync.sh --assign Gfermoto` (aligns board status/flow with issue state, assigns open issues without assignee, reports open issues missing subtask checklists). Checklist: root **[CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md)** § *Issues & Project board*. **Deferred ideas** may live only in this ROADMAP until a new scoped issue is filed.

---

## Future work candidates

Prioritize by capacity; open a new **GitHub issue** when work is scoped (see [CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md)).

| Theme | Why |
|-------|-----|
| **Accessibility (a11y)** | [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117) ✅ baseline **v0.2.9**: skip link, focus, contrast, axe E2E, [A11Y.md](../../archive/internal/docs-legacy/A11Y.md); further work via new issues. |
| **Broader E2E (Playwright)** | [#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118) ✅ issue closed: smoke suites + scheduled CI — [TESTING.md](./testing.md); more journeys added incrementally in PRs. |
| **Secrets in production** | [#119](https://github.com/Gfermoto/BirdLense-Hub/issues/119) ✅: runbook [SECRETS_ROTATION.md](../../archive/internal/docs-legacy/SECRETS_ROTATION.md) (complements [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47)). |
| **Stack version sync** | [#120](https://github.com/Gfermoto/BirdLense-Hub/issues/120) ✅: checklist + `python3 scripts/check-docs-version.py` — see [VERSIONING](../../archive/internal/docs-legacy/VERSIONING.md). |
| **Community / donation UX** | [#121](https://github.com/Gfermoto/BirdLense-Hub/issues/121) ✅ MVP: `general.donate_url` drives links in Navigation (desktop + mobile + gear menu) and Food card; see [CONFIGURATION.md](../user/configuration.md). Click analytics out of scope. |
| **Interactive life list (planning)** | [#125](https://github.com/Gfermoto/BirdLense-Hub/issues/125) ✅ issue closed: same intent — manual flags/notes vs migration table; open a new issue when a spec exists. |
| **Species canonical registry** | [#168](https://github.com/Gfermoto/BirdLense-Hub/issues/168) ✅: unified registry, name normalization, backfill, background metadata jobs, CI quality gate for the full dataset. |

### User wishes backlog (Apr 2026)

Tracked as separate issues; acceptance criteria live in each issue.

**Preparation before coding ([#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131), [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139)):** [pre-implementation checklist](../../archive/internal/docs-legacy/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.md) (maintainer notes in the repository; omitted from the static documentation site).

**Progress update (Apr 2026):**
- [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117) — a11y baseline shipped in **v0.2.9** (PR [#187](https://github.com/Gfermoto/BirdLense-Hub/pull/187), release [#188](https://github.com/Gfermoto/BirdLense-Hub/pull/188)); see [A11Y.md](../../archive/internal/docs-legacy/A11Y.md).
- [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139) — shipped and closed: Unknowns nav removed, `/unknowns` legacy redirect to `/timeline?review=1`, Timeline review mode (chip + counter), OpenAPI + API tests + smoke redirect coverage.
- [#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131) — shipped and closed: catalog nav reshaped toward the seasonality table; **current UI (v0.3.7+):** nav **Species** → `/species` (same grid as `/migration-calendar`, which remains an alias URL); card directory → `/species-directory`; deep links `/species/:id` preserved. (Issue text described an intermediate redirect-only `/species` — no longer accurate.)
- [#127](https://github.com/Gfermoto/BirdLense-Hub/issues/127) — shipped and closed: region comparison block moved from Overview to Migration; leftover Overview pointer removed.
- [#130](https://github.com/Gfermoto/BirdLense-Hub/issues/130) — shipped and closed: Overview species distribution chart (slice and legend) now drills down to Timeline with species/date filters.
- [#133](https://github.com/Gfermoto/BirdLense-Hub/issues/133) — shipped and closed: Migration page now supports day-level date-range filtering for the migration table while keeping regional reference block unfiltered.
- [#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129), [#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153), [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157) — shipped and closed: BirdNET MQTT bias, multi-camera confidence boost, recording post-roll; see [CONFIGURATION.md](../user/configuration.md) → Processor.
- [#114](https://github.com/Gfermoto/BirdLense-Hub/issues/114), [#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118), [#125](https://github.com/Gfermoto/BirdLense-Hub/issues/125), [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163)–[#166](https://github.com/Gfermoto/BirdLense-Hub/issues/166) — issues closed for a zero-open backlog tail: UX gate in [CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md), E2E note in [TESTING.md](./testing.md), other ideas in the tables below + consilium item 17.
- [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167) — **closed:** scales — MQTT/HA, **weight spike → recording**, per-clip **delta** on video page, HA settings split, perf defaults; optional auto-tare out of scope.
- [#228](https://github.com/Gfermoto/BirdLense-Hub/issues/228) — **closed:** scale **delta on visit card** (timeline/overview) like feeder/weather.
- [#243](https://github.com/Gfermoto/BirdLense-Hub/issues/243) — **open QA gate:** field acceptance for feeder scales (ESPHome HX711 + hub). Before running tests: move the issue card on [BirdLense Hub — Roadmap](https://github.com/users/Gfermoto/projects/2) to **Ready** (or assign + date), deploy hub code, and set `integrations.scales.*` to match your MQTT prefix/units (`g`); checklist is in the issue body.

| # | Issue | Summary |
|---|--------|--------|
| [#127](https://github.com/Gfermoto/BirdLense-Hub/issues/127) | Regional top + overlap with recognized | ✅ Compare-to-region on Migration (see progress above) |
| [#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128) | Auto thresholds for regional top | ✅ Processor merge + settings; delta/floor from `min_confidence_to_process`; manual overrides win; [CONFIGURATION.md](../user/configuration.md) |
| [#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129) | Thresholds + MQTT BirdNET | ✅ Lower classifier thresholds for species in recent BirdNET MQTT: `birdnet_mqtt_auto_confidence` + delta/floor; [CONFIGURATION.md](../user/configuration.md) |
| [#130](https://github.com/Gfermoto/BirdLense-Hub/issues/130) | Overview second chart | Click species → today’s recordings for that species |
| [#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131) | Migration as catalog entry | Historical: nav toward seasonality table; **now** `/species` + `/migration-calendar` (same UI), `/species-directory` (cards), `/species/:id` |
| [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139) | Unknowns + Timeline | Remove Unknowns nav; review mode on Timeline (chip + badge; redirect legacy URL) |
| [#132](https://github.com/Gfermoto/BirdLense-Hub/issues/132) | Species filters | ✅ Bird Directory «Regional» = eBird regional top + `birdnet_mqtt` detections; `regional_scope` on `GET /species`; [CONFIGURATION.md](../user/configuration.md) |
| [#133](https://github.com/Gfermoto/BirdLense-Hub/issues/133) | Period on Migration | **Day-level date range**; table + heard/recognized; not regional |
| [#134](https://github.com/Gfermoto/BirdLense-Hub/issues/134) | Food list for Europe | ✅ expanded `seed.py` + idempotent merge by name; [CONFIGURATION.md](../user/configuration.md) → Bird food |
| [#136](https://github.com/Gfermoto/BirdLense-Hub/issues/136) | eBird `species_mapping` | ✅ `GET /api/ui/settings/ebird-species-mapping-suggestions`, Settings UI button, shared eBird top cache; [CONFIGURATION.md](../user/configuration.md) |

**New ideas (Apr 2026) — table keeps historical GitHub numbers; open a new issue when work starts:**

| # | Theme | Issue | Priority / area |
|---|--------|-------|-----------------|
| 1 | System: unique visitor counter | [#151](https://github.com/Gfermoto/BirdLense-Hub/issues/151) ✅ | P3, web |
| 2 | After deleting a recording, return to list not Home | [#152](https://github.com/Gfermoto/BirdLense-Hub/issues/152) ✅ | P2, web, bug |
| 3 | Multi-camera confidence for cameras at one location | [#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153) ✅ `multi_camera_groups` + boost after merge; [CONFIGURATION.md](../user/configuration.md) | P2, processor |
| 4 | “Daily pattern” chart: click should filter by hour | [#154](https://github.com/Gfermoto/BirdLense-Hub/issues/154) ✅ | P2, web, bug |
| 5 | Recording duration mismatch (Home vs recording page) | [#155](https://github.com/Gfermoto/BirdLense-Hub/issues/155) ✅ | P2, web, bug |
| 6 | Review counter not updating without full reload | [#156](https://github.com/Gfermoto/BirdLense-Hub/issues/156) ✅ | P2, web, bug |
| 7 | Recording quality: pre-roll/post-roll for approach/departure | [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157) ✅ `processor.post_record_seconds` (recording tail); pre-roll remains `video.pre_record_seconds` (Go2RTC — see issue) | P2, processor |
| 8 | Re-export: orphan recognitions without species/recording | [#158](https://github.com/Gfermoto/BirdLense-Hub/issues/158) ✅ | P1, processor, bug |
| 9 | UX consistency: tooltips and inline help | [#159](https://github.com/Gfermoto/BirdLense-Hub/issues/159) ✅ | P3, web |
| 10 | Regenerate tracks: progress, 409, timeouts on large sets | [#160](https://github.com/Gfermoto/BirdLense-Hub/issues/160) ✅ | P1, web, bug |
| 11 | Dataset UX: clear Library flow (DB maintenance + export) | [#161](https://github.com/Gfermoto/BirdLense-Hub/issues/161) ✅ | P2, docs + web |
| 12 | Dataset pipeline: less post-script work before training | [#162](https://github.com/Gfermoto/BirdLense-Hub/issues/162) ✅ | P2, processor |
| 13 | Detector: non-bird classes (rodents, cats, …) | [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) ✅ issue closed; tracker: [consilium item 17](#detection-strategy-consilium); new issue when training starts | P3, processor, research |
| 14 | Classifier: transfer learning (US + local dataset) | [#164](https://github.com/Gfermoto/BirdLense-Hub/issues/164) ✅ issue closed; idea retained here; new issue when work starts | P2, processor, research |
| 15 | Telegram: SOCKS5h proxy in UI and MTProto (`apihelper.proxy`) | [#165](https://github.com/Gfermoto/BirdLense-Hub/issues/165) ✅ issue closed; idea retained here; new issue when work starts | P3, web |
| 16 | Heimdall manual widgets / docs | [#166](https://github.com/Gfermoto/BirdLense-Hub/issues/166) ✅ docs direction retained; no runtime integration promised | P3, infra |
| 17 | Scales: trigger + per-clip delta + video UI ✅ ([#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167) closed); visit card ✅ ([#228](https://github.com/Gfermoto/BirdLense-Hub/issues/228) closed); field acceptance — [#243](https://github.com/Gfermoto/BirdLense-Hub/issues/243) (open until run) | — | P3, web + API |
| 18 | **ML / video: bird action recognition** (land, leave, forage, drink, aggression, …) — **any** deployment: feeders, parks/reserves over IP cameras, etc.; separate from per-frame species ID | [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379) — **open execution track** (model selection and integration) with research context; related: [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157) (clip capture), [#164](https://github.com/Gfermoto/BirdLense-Hub/issues/164) (species TL). **Research:** [§ below](#bird-behavior-ml-research) | P3, processor, ML, research |

<h3 id="bird-behavior-ml-research">Research: bird behaviors on video (short)</h3>

Analogous work **exists in datasets and papers**; few off-the-shelf solutions cover **your** scene out of the box (backyard feeders at any complexity, park/reserve IP cameras, wetland hides, …) — expect custom labels, fine-tuning, or hybrid signals (e.g. scales only where installed).

| Track | Notes |
|-------|--------|
| **Visual WetlandBirds** (2025, [Scientific Data](https://www.nature.com/articles/s41597-025-05516-5), [arXiv](https://arxiv.org/abs/2501.08931), [code](https://github.com/3dperceptionlab/visual-wetlandbirds)) | **178** videos, **858** behavior clips (~**20 s** mean, ~**59 min** total), **13** species, **7** behaviors: Alert, Feeding, Flying, Preening, Resting, Swimming, Walking — **per-frame** bbox + species. Behavior baselines (accuracy): Video ResNet **0.56**, MViT/Swin **0.51**, TimeSFormer **0.49**, S3D **0.29**; species detection (YOLOv9): mAP50 **0.801**. Capture domain: Spanish wetlands (visual world **≠** typical feeder rig or a fixed park pole). Details — [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379). |
| **Automated ethograms / event segmentation** | **Kagu nest** ([Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.kh18932bb), IJCV [2023](https://doi.org/10.1007/s11263-023-01781-2)): **~253 h** @25 FPS (**~23M** frames), bbox + **5** events (Feeding, Pushing/Throwing leaves, Walk-In/Out) + lighting; untrimmed stream segmentation. See [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379). |
| **Practical path for the hub** | Often: **track** (bbox) + clip classifier (TSN / SlowFast / VideoMAE), or **weak cues** (feeders: scales + detection; parks/reserves: vision-only / track heuristics). Explicit land/leave usually needs labels or rules on tracks / clip boundaries. |

**System initiative (P1):**

- [#168](https://github.com/Gfermoto/BirdLense-Hub/issues/168) — **Species Canonical Registry** epic: canonical registry, universal name resolver, history migration, metadata enrichment, CI invariants (not one-off per-species patches).
- Phases closed: [#169](https://github.com/Gfermoto/BirdLense-Hub/issues/169) ✅ SSOT registry · [#170](https://github.com/Gfermoto/BirdLense-Hub/issues/170) ✅ universal resolver · [#171](https://github.com/Gfermoto/BirdLense-Hub/issues/171) ✅ backfill/repair · [#172](https://github.com/Gfermoto/BirdLense-Hub/issues/172) ✅ background metadata jobs · [#173](https://github.com/Gfermoto/BirdLense-Hub/issues/173) ✅ observability + CI quality gate.
- Outcome (Mar 2026 — registry epic completed): production `processed=806`, `matched=806`, `unresolved=0` on startup; APIs `seed/backfill/unresolved/health/enrich`, async enrichment status, CI smoke for the registry.

---

## Shipped ideas (archive)

Historical **simple → complex** checklist (all rows shipped). Cross-check [FEATURES](../user/features.md); do **not** treat this table as a to-do list.

| Idea | Notes | Complexity |
|------|--------|--------------|
| ✅ Playback speed 0.5× / 2× | Video player (`VideoPlayer/index.tsx`) | Low |
| ✅ Webhook on detection | `webhook.url` + POST from processor | Low |
| ✅ CSV/JSON timeline export | `/api/ui/timeline/export` + Timeline UI | Low |
| ✅ “Last bird” Overview widget | See Overview | Low |
| ✅ Timeline time-of-day filter | Timeline (+ Unknowns) | Low |
| ✅ PWA improvements | Vite PWA, install prompt, update prompt | Low |
| ✅ Unknowns page | Low-confidence review | Medium |
| ✅ Monthly PDF report | System / reports | Medium |
| ✅ Xeno-canto on species page | Bird directory | Medium |
| ✅ eBird export | Timeline export menu | Medium |
| ✅ Prometheus / Grafana | `/metrics`, `/api/metrics` | Medium |
| ✅ Per-species confidence overrides | Settings | Medium |
| ✅ iNaturalist crop export | Species / export flows | Medium |
| ✅ Web Push | Settings (notifications) | Medium |
| ✅ Migration calendar | Overview / patterns | High |
| ✅ Region comparison (eBird) | Overview card | High |
| ✅ Sun/moon card on weather | Overview / weather | Low |
| ✅ Video prev/next (same UTC day) | Video details + `GET /api/ui/videos/:id/neighbors` ([#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82)) | Low |

**Note:** For **new** ideas use [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions) or an Issue per the triage table above.

### UX improvements (shipped)

| Item | Status |
|------|--------|
| Activity month picker | Shipped (v0.1.8) |
| Unknowns empty state | Shipped |
| Unknowns time-of-day filter | Shipped (v0.1.9) |

---

<h2 id="completion-then-operator-testing">Work order: finish in-flight work, then operator testing</h2>

**Feeder scales (before field run, short):**

1. **Hub (`user_config.yaml`):** `integrations.scales.enabled: true`. Use **`source: mqtt`** (recommended for the repo firmware) with `mqtt_topic_prefix: birdlense/scale` so the hub derives `…/weight`, `…/bird_present`, `…/command`; or **`source: esphome`** for direct ESPHome Web API live snapshot only (no processor MQTT history / spike trigger from that path).
2. **Overview card:** the “Feeder scale” block uses **`GET /api/ui/feed/info`** — weight, bird chip, MQTT tare, empty/stale hints. The **feeder relay is optional** for scales to show.
3. **GitHub board:** issue [#243](https://github.com/Gfermoto/BirdLense-Hub/issues/243) → column **Ready** before the run; after the checklist — comment + close.

**Agreement:** first **complete** the agreed slice of work (open issues in the current wave / **BirdLense Hub — Roadmap** milestone: PR merged, issue **closed**, **`make deploy`** if needed, CI green). **Then** the operator runs **manual testing** on the live hub and files **feedback as new issues** (or flags regressions on an existing issue) — without growing the same wave in parallel.

**Backlog vs acceptance:** rows in **New ideas** without ✅ are **future queue**; only items **explicitly in progress** on the board count toward “ready for acceptance”. The **detection consilium** ([item 17](#detection-strategy-consilium)) runs **after** the current wave stabilizes unless the board decides otherwise.

---

## Tech debt queue (simple → complex)

**Execution lives in GitHub issues and the [BirdLense Hub — Roadmap](https://github.com/users/Gfermoto/projects/2) board**; this section is a pointer only.

- Navigator: [#220](https://github.com/Gfermoto/BirdLense-Hub/issues/220). **Sub-issues** (board hierarchy): [#198](https://github.com/Gfermoto/BirdLense-Hub/issues/198) (**closed** — split `ui_routes` into domain `ui_*_routes`, see [ARCHITECTURE](./architecture.md)), [#201](https://github.com/Gfermoto/BirdLense-Hub/issues/201) (**closed** — processor modularization, HA `user_config` migration, PR [#237](https://github.com/Gfermoto/BirdLense-Hub/pull/237)), [#238](https://github.com/Gfermoto/BirdLense-Hub/issues/238) (processor **phase 2** **done** — `MotionRecordingSession`, MQTT queue, **ebird_region_core**), [#221](https://github.com/Gfermoto/BirdLense-Hub/issues/221) · [#222](https://github.com/Gfermoto/BirdLense-Hub/issues/222) · [#223](https://github.com/Gfermoto/BirdLense-Hub/issues/223) · [#224](https://github.com/Gfermoto/BirdLense-Hub/issues/224) (**closed** — MQTT outbound queue, `frame_processor` no sleep) · [#225](https://github.com/Gfermoto/BirdLense-Hub/issues/225) (**done** on Hub: Alembic `001` + `MotionRecordingSession`; further checklist in issue). Re-link: `bash scripts/github-issue-link-subissues.sh 220 198 201 238 221 222 223 224 225`. RU: [ROADMAP.ru.md](../contributor/roadmap.md) (wave D). Not this wave: [#164](https://github.com/Gfermoto/BirdLense-Hub/issues/164); Heimdall/HA backlog [#229](https://github.com/Gfermoto/BirdLense-Hub/issues/229)–[#234](https://github.com/Gfermoto/BirdLense-Hub/issues/234) (**#234** ✅ — [Heimdall tiles](../../archive/internal/docs-legacy/HEIMDALL.md)).

**Architecture & maintainability (next wave, Apr 2026):** same [Roadmap project board](https://github.com/users/Gfermoto/projects/2) — [#292](https://github.com/Gfermoto/BirdLense-Hub/issues/292) (decompose `app/web/app.py`: extensions, errors, startup), [#293](https://github.com/Gfermoto/BirdLense-Hub/issues/293) (service layer / thin routes), [#281](https://github.com/Gfermoto/BirdLense-Hub/issues/281) (Pydantic on mutating APIs), [#294](https://github.com/Gfermoto/BirdLense-Hub/issues/294) (N+1 / DB indexes), [#295](https://github.com/Gfermoto/BirdLense-Hub/issues/295) (**baseline ✅** — bootstrap + `DetectionStrategy` ABC + `DetectionStrategyProtocol`, see [ARCHITECTURE](./architecture.md) § Maintainability baseline), [#296](https://github.com/Gfermoto/BirdLense-Hub/issues/296) (TanStack Query on primary routes — **phase 1**; Context / prop-drilling polish stays in issue), [#297](https://github.com/Gfermoto/BirdLense-Hub/issues/297) (CI: complexity metrics, OpenAPI→TS; npm audit policy → **#284** ✅). **Security / hardening:** [#277](https://github.com/Gfermoto/BirdLense-Hub/issues/277)–[#286](https://github.com/Gfermoto/BirdLense-Hub/issues/286) (Docker non-root, secrets, API auth, session timeout, nginx recordings, CORS, ESLint imports). **#284** ✅ **closed** — scheduled **npm audit** for `app/ui`; [TESTING](./testing.md). **#287** ✅ **closed** — audit: no `ALTER TABLE` in `create_app` / web runtime; DDL via Alembic only; [ARCHITECTURE](./architecture.md) § Database.

---

## Near-term priorities (public)

| Priority | Focus |
|----------|--------|
| **Community** | [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions), `good first issue` triage, docs feedback |
| **Quality** | CI on PRs — see [TESTING](./testing.md) §1 (Bandit, pip-audit, Ruff, OpenAPI contract, UI build, MkDocs, Docker tests + Playwright smoke + catalog audit); Dependabot |
| **Docs** | `VERSION` aligned with `mkdocs.yml`, `app/ui/package.json`, and `app/web/openapi.yaml` (`scripts/check-docs-version.py`); interactive OpenAPI (Redoc) on the doc site |
| **Releases** | Tags + GitHub Release → Docker semver image + Pages deploy |
| **Public release gate** | Unified runbook: [PUBLIC_RELEASE_CHECKLIST](../../archive/internal/docs-legacy/PUBLIC_RELEASE_CHECKLIST.md) + [RELEASE_READINESS](https://github.com/Gfermoto/BirdLense-Hub/blob/main/release-readiness.md) |

### Scale (#418): motion, queue, Postgres ([#424](https://github.com/Gfermoto/BirdLense-Hub/issues/424) — **закрыт**, релизные подзадачи 2026-05)

Эпик вёл треки B1–B3 отдельными PR (см. закрытые [#432](https://github.com/Gfermoto/BirdLense-Hub/issues/432)–[#434](https://github.com/Gfermoto/BirdLense-Hub/issues/434)).

| Track | Результат (MVP) | Где смотреть |
|-------|-----------------|--------------|
| **B1** | Gauge/счётчики деградации `triggers.*` + MQTT в `processor_runtime_stats.json`; fallback motion фабрики учитывается | [PROCESSOR_PERFORMANCE](../user/processor-performance.md) § Trigger path observability; [TROUBLESHOOTING](../user/troubleshooting.md#processor-trigger-metrics) |
| **B2** | Задокументированы лимиты и метрики существующих очередей (`mqtt.publish_queue_max`, outbound / Frigate / scales drops); единый «heavy job executor» — при необходимости новое issue | [PROCESSOR_PERFORMANCE](../user/processor-performance.md#queues-backpressure) |
| **B3** | Операторский Postgres runbook | [POSTGRES_MIGRATION](../../archive/internal/docs-legacy/POSTGRES_MIGRATION.md) |

Родитель фазы: [#418](https://github.com/Gfermoto/BirdLense-Hub/issues/418).

The **shipped archive** and other historical tables earlier in this document are not a live backlog. Active work is the **consilium** issues and **future candidates**; always cross-check [FEATURES](../user/features.md).

---

## See also

[ACCESS_CONTROL](./access-control.md) · [DATASETS](./datasets.md) · [TESTING](./testing.md) · [CONFIGURATION](../user/configuration.md)
