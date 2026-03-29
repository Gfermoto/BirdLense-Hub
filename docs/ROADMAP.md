# Roadmap — BirdLense Hub

Direction of travel and current stack. **Shipped items** are summarized here; details live in [Changelog](./project/changelog.md) and [FEATURES](./FEATURES.md).

[Русский](./ROADMAP.ru.md)

---

## Current stack (March 2026)

| Component | Version / note |
|-----------|----------------|
| **Ultralytics** | 8.4.21 (Docker base image) |
| **Platform** | **x86/amd64 only** (Intel or AMD 64-bit). ARM / Apple Silicon / aarch64 — **not supported, not planned** |
| **Detection** | `two_stage`: binary `.pt` + YOLO11n-cls (EU); `single_stage` fallback if weights missing |
| **EU classifier** | `best.pt` — birds-525 + iNaturalist (~491 species) |
| **US classifier** | `best_US.pt` — NABirds (fallback) |
| **React** | 19.2.4 |
| **Vite** | 6.4.1 |

---

## Recently delivered (high level)

- **Home Assistant** — MQTT discovery (e.g. last species, bird-detected). See [CONFIGURATION](./CONFIGURATION.md) → MQTT.
- **Dataset pipeline** — `best_frame` in YOLO layout, ZIP export (`GET /api/ui/dataset/export`), relabel moves on-disk crops. **System → Storage**.
- **Video prev/next (same UTC day)** — [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) closed (**v0.2.6**): `GET /api/ui/videos/:id/neighbors` + arrows on video details (browse clips for that calendar day in UTC without losing list context).
- **Overview mean recording duration** — [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) closed: metric is the average length of **one clip** (`Video`), not a visit aggregate; PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106).
- **Public gallery (opt-in)** — [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) closed (v0.2.4): background upload runs inside **Flask app context**; troubleshooting in [CONFIGURATION](./CONFIGURATION.md) → Gallery.
- **System: resource charts with server-side history** — SQLite `system_resource_sample`, `GET /api/ui/system/metrics/history`, UI windows 6/24/48 h plus live tail; tune with `BIRDLENSE_SYSTEM_METRICS_*` — [CONFIGURATION](./CONFIGURATION.md) → Prometheus / Grafana.

---

## Backlog consilium (March 2026)

**Brainstorm roles:** product (operator value), security, platform/infra, ML & data, integrations (MQTT/HA/Frigate), UX, docs & OSS hygiene.

**Outcome:** triaged items are **GitHub Issues** (not shipped until closed in a release): [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57), [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) (operator UX — Mar 2026; phase B: Unknowns snackbar **Open video**). **Done:** [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) (git-history secret scan + SECURITY updates), [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) (`export_birdlense_to_yolo.py`), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) (MQTT reconnect backoff + missed-events docs clarity), [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) (SQLite backup/restore in System UI + INSTALL/TROUBLESHOOTING updates), [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) (locale switch + pilot `de` locale), [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) (scheduled smoke for published `ghcr` image), [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) (OpenAPI contract smoke in CI + local run command), [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) (gallery upload thread app context, v0.2.4), [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) (same-UTC-day video prev/next, v0.2.6), [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) (local TZ / cross-day / docs), [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) (Overview: mean duration = **per-`Video`** average, not visit span). [#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) (ARM Docker) is **closed** — x86-only; not part of this backlog.

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
| 6 | UI i18n framework | [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) ✅ locale switch + pilot `de` | `area:web`, P3 |
| 7 | CI: scheduled image smoke test | [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) ✅ workflow `Docker image smoke (published)` (`ghcr ... :latest` + `/api/ui/health`) | `area:infra`, P3 |
| 8 | CI: OpenAPI contract tests | [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) ✅ `openapi-contract` in CI + `web/tests/test_openapi_contract.py` | `area:web`, P3 |
| 9 | Yearly species checklist / life list | [#55](https://github.com/Gfermoto/BirdLense-Hub/issues/55) ✅ Migration page: year filter + table (rows and Σ) — no duplicate checklist block | `area:web`, P3 |
| 10 | CORS demo host → config/env | [#56](https://github.com/Gfermoto/BirdLense-Hub/issues/56) ✅ demo host moved out of hardcoded CORS defaults into `CORS_DEFAULT_ORIGINS` / `CORS_ORIGINS` | `area:web`, P3 |
| 11 | Docs: Prometheus alert examples | [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) ✅ `examples/prometheus/`, [CONFIGURATION](./CONFIGURATION.md) | `area:docs`, P3 |
| 12 | Gallery: investigate / fix (opt-in public gallery) | [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) ✅ app context in upload thread + docs/tests v0.2.4 | `area:web`, P2, `bug` |
| 13 | Manual species correction: unify Unknowns vs in-video flow | [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) ✅ phases A+B+C: shared API + Unknowns **Open video** snackbar + recent shared correction history | `area:web`, P2 |
| 14 | Video navigation: sequential browse (e.g. same day), no list reset | [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) ✅ UI + `GET /videos/:id/neighbors` **v0.2.6** | `area:web`, P2 |
| 15 | Video neighbors: local TZ, cross-day jump, docs clarity (follow-up to #82) | [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) ✅ local day + `cross_day` + API/UI docs | `area:web`, P3 |
| 16 | Overview: “mean duration” used visit span instead of per-recording average | [#107](https://github.com/Gfermoto/BirdLense-Hub/issues/107) ✅ mean over `Video` rows (PR [#106](https://github.com/Gfermoto/BirdLense-Hub/pull/106)); RU/EN labels | `area:web`, P3, `bug` |
| 17 | Detection: false positives and inanimate objects — strategy (two_stage vs single_stage+COCO, thresholds, weights) | Consilium: [§ below](#detection-strategy-consilium) · ties to [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) | P2, processor, ML |

### Detection strategy consilium {#detection-strategy-consilium}

**Goal:** run a consilium (product/operator, ML, platform) and record a decision on reducing **false positives** and **non-living object** detections in production. By default this runs **after** the current development wave is closed and basic manual acceptance; see [§ Finish work, then operator testing](#completion-then-operator-testing).

**Context:** with `detection_strategy: two_stage` and values in `user_config.yaml`, behavior **does not** match **single_stage** + typical COCO, where the default **animals-only** auto-filter applies (`processor.single_stage_coco_animals_only_auto` — excludes person and inanimate COCO classes). Deploying code does not overwrite `user_config.yaml`.

**Options to compare (combinations allowed):**

- keep **two_stage** and tune **`min_confidence_binary`** / **`min_confidence_to_process`**, and/or retrain/replace the binary detector;
- move to **single_stage** + COCO (or another detect model) and rely on the animal filter / custom classes;
- factor in Frigate / extra motion triggers.

See [CONFIGURATION.md](./CONFIGURATION.md) (processor, motion). Non-bird classes overlap [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) — consilium should decide one epic vs child issues.

**Do not forget (checklist):**

| Step | Action |
|------|--------|
| 1 | Capture the live hub **`processor`** snippet from `user_config.yaml`: `detection_strategy`, `models.binary` / `models.classifier` / `models.single_stage`, `min_confidence_binary`, `min_confidence_to_process`, `single_stage_coco_animals_only_auto`. |
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

**Reporting (all shipped work, not only consilium):** every shipped item has a **GitHub Issue** (open one if missing) and, when tracked, a card on **BirdLense Hub — Roadmap**. When done: comment (outcome + PR links), **close** the issue, set board **Status → Done** (with a PAT: `bash scripts/github-project-mark-done.sh <n>`). For routine hygiene, run `bash scripts/github-project-sync.sh --assign Gfermoto` (aligns board status/flow with issue state, assigns open issues without assignee, reports open issues missing subtask checklists). Checklist: root **[CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md)** § *Issues & Project board*.

---

## Future work candidates (issues created)

These themes are now tracked as dedicated **Issues** and added to the board; schedule by available capacity:

| Theme | Why |
|-------|-----|
| **Accessibility (a11y)** | [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117) ✅ baseline **v0.2.9**: skip link, focus, contrast, axe E2E, [A11Y.md](./A11Y.md); further work via new issues. |
| **Broader E2E (Playwright)** | [#118](https://github.com/Gfermoto/BirdLense-Hub/issues/118): beyond smoke — login, timeline, critical settings, correction flow. |
| **Secrets in production** | [#119](https://github.com/Gfermoto/BirdLense-Hub/issues/119) ✅: runbook [SECRETS_ROTATION.md](./SECRETS_ROTATION.md) (complements [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47)). |
| **Stack version sync** | [#120](https://github.com/Gfermoto/BirdLense-Hub/issues/120) ✅: checklist + `python3 scripts/check-docs-version.py` — see [VERSIONING](./VERSIONING.md). |
| **Community / donation UX** | [#121](https://github.com/Gfermoto/BirdLense-Hub/issues/121) ✅ MVP: `general.donate_url` drives links in Navigation (desktop + mobile + gear menu) and Food card; see [CONFIGURATION.md](./CONFIGURATION.md). Click analytics out of scope. |
| **Interactive life list (planning)** | [#125](https://github.com/Gfermoto/BirdLense-Hub/issues/125): manual “I saw it” flags and notes — distinct from the migration matrix; backlog/planning in the issue first, no implementation yet. |
| **Species canonical registry** | [#168](https://github.com/Gfermoto/BirdLense-Hub/issues/168) ✅: unified registry, name normalization, backfill, background metadata jobs, CI quality gate for the full dataset. |

### User wishes backlog (Mar 2026)

Tracked as separate issues; acceptance criteria live in each issue.

**Preparation before coding ([#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131), [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139)):** [pre-implementation checklist](./PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.md).

**Progress update (Mar 2026):**
- [#117](https://github.com/Gfermoto/BirdLense-Hub/issues/117) — a11y baseline shipped in **v0.2.9** (PR [#187](https://github.com/Gfermoto/BirdLense-Hub/pull/187), release [#188](https://github.com/Gfermoto/BirdLense-Hub/pull/188)); see [A11Y.md](./A11Y.md).
- [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139) — shipped and closed: Unknowns nav removed, `/unknowns` legacy redirect to `/timeline?review=1`, Timeline review mode (chip + counter), OpenAPI + API tests + smoke redirect coverage.
- [#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131) — shipped and closed: Catalog menu entry removed, legacy `/species` redirects to `/migration-calendar`, species deep links (`/species/:id`) preserved.
- [#127](https://github.com/Gfermoto/BirdLense-Hub/issues/127) — shipped and closed: region comparison block moved from Overview to Migration; leftover Overview pointer removed.
- [#130](https://github.com/Gfermoto/BirdLense-Hub/issues/130) — shipped and closed: Overview species distribution chart (slice and legend) now drills down to Timeline with species/date filters.
- [#133](https://github.com/Gfermoto/BirdLense-Hub/issues/133) — shipped and closed: Migration page now supports day-level date-range filtering for the migration table while keeping regional reference block unfiltered.

| # | Issue | Summary |
|---|--------|--------|
| [#127](https://github.com/Gfermoto/BirdLense-Hub/issues/127) | Regional top + overlap with recognized | ✅ Compare-to-region on Migration (see progress above) |
| [#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128) | Auto thresholds for regional top | ✅ Processor merge + settings; delta/floor from `min_confidence_to_process`; manual overrides win; [CONFIGURATION.md](./CONFIGURATION.md) |
| [#129](https://github.com/Gfermoto/BirdLense-Hub/issues/129) | Thresholds + MQTT BirdNET | Extra sensitivity; **7-day** hint window (when BirdNET is configured) |
| [#130](https://github.com/Gfermoto/BirdLense-Hub/issues/130) | Overview second chart | Click species → today’s recordings for that species |
| [#131](https://github.com/Gfermoto/BirdLense-Hub/issues/131) | Migration as catalog entry | **Remove catalog from nav**; migration table primary path to species; clicks → `/species/:id`; in-page tabs = table modes |
| [#139](https://github.com/Gfermoto/BirdLense-Hub/issues/139) | Unknowns + Timeline | Remove Unknowns nav; review mode on Timeline (chip + badge; redirect legacy URL) |
| [#132](https://github.com/Gfermoto/BirdLense-Hub/issues/132) | Species filters | ✅ Bird Directory «Regional» = eBird regional top + `birdnet_mqtt` detections; `regional_scope` on `GET /species`; [CONFIGURATION.md](./CONFIGURATION.md) |
| [#133](https://github.com/Gfermoto/BirdLense-Hub/issues/133) | Period on Migration | **Day-level date range**; table + heard/recognized; not regional |
| [#134](https://github.com/Gfermoto/BirdLense-Hub/issues/134) | Food list for Europe | ✅ expanded `seed.py` + idempotent merge by name; [CONFIGURATION.md](./CONFIGURATION.md) → Bird food |
| [#136](https://github.com/Gfermoto/BirdLense-Hub/issues/136) | eBird `species_mapping` | ✅ `GET /api/ui/settings/ebird-species-mapping-suggestions`, Settings UI button, shared eBird top cache; [CONFIGURATION.md](./CONFIGURATION.md) |

**New ideas (Mar 2026) — tracked as issues on the Project board:**

| # | Theme | Issue | Priority / area |
|---|--------|-------|-----------------|
| 1 | System: unique visitor counter | [#151](https://github.com/Gfermoto/BirdLense-Hub/issues/151) ✅ | P3, web |
| 2 | After deleting a recording, return to list not Home | [#152](https://github.com/Gfermoto/BirdLense-Hub/issues/152) ✅ | P2, web, bug |
| 3 | Multi-camera confidence for cameras at one location | [#153](https://github.com/Gfermoto/BirdLense-Hub/issues/153) | P2, processor |
| 4 | “Daily pattern” chart: click should filter by hour | [#154](https://github.com/Gfermoto/BirdLense-Hub/issues/154) ✅ | P2, web, bug |
| 5 | Recording duration mismatch (Home vs recording page) | [#155](https://github.com/Gfermoto/BirdLense-Hub/issues/155) ✅ | P2, web, bug |
| 6 | Review counter not updating without full reload | [#156](https://github.com/Gfermoto/BirdLense-Hub/issues/156) ✅ | P2, web, bug |
| 7 | Recording quality: pre-roll/post-roll for approach/departure | [#157](https://github.com/Gfermoto/BirdLense-Hub/issues/157) | P2, processor |
| 8 | Re-export: orphan recognitions without species/recording | [#158](https://github.com/Gfermoto/BirdLense-Hub/issues/158) ✅ | P1, processor, bug |
| 9 | UX consistency: tooltips and inline help | [#159](https://github.com/Gfermoto/BirdLense-Hub/issues/159) ✅ | P3, web |
| 10 | Regenerate tracks: progress, 409, timeouts on large sets | [#160](https://github.com/Gfermoto/BirdLense-Hub/issues/160) ✅ | P1, web, bug |
| 11 | Dataset UX: clear Library flow (DB maintenance + export) | [#161](https://github.com/Gfermoto/BirdLense-Hub/issues/161) ✅ | P2, docs + web |
| 12 | Dataset pipeline: less post-script work before training | [#162](https://github.com/Gfermoto/BirdLense-Hub/issues/162) ✅ | P2, processor |
| 13 | Detector: non-bird classes (mice, squirrels, cats) | [#163](https://github.com/Gfermoto/BirdLense-Hub/issues/163) · see consilium [item 17](#detection-strategy-consilium) | P3, processor, research |
| 14 | Classifier: transfer learning (US + local dataset) | [#164](https://github.com/Gfermoto/BirdLense-Hub/issues/164) | P2, processor, research |
| 15 | Telegram: SOCKS5h proxy in UI and MTProto (`apihelper.proxy`) | [#165](https://github.com/Gfermoto/BirdLense-Hub/issues/165) | P3, web |
| 16 | Heimdall integration | [#166](https://github.com/Gfermoto/BirdLense-Hub/issues/166) | P3, infra |
| 17 | Long-term: feeder / bird scales (auto-tare + object detection) | [#167](https://github.com/Gfermoto/BirdLense-Hub/issues/167) | P3, processor, research |

**System initiative (P1):**

- [#168](https://github.com/Gfermoto/BirdLense-Hub/issues/168) — **Species Canonical Registry** epic: canonical registry, universal name resolver, history migration, metadata enrichment, CI invariants (not one-off per-species patches).
- Phases closed: [#169](https://github.com/Gfermoto/BirdLense-Hub/issues/169) ✅ SSOT registry · [#170](https://github.com/Gfermoto/BirdLense-Hub/issues/170) ✅ universal resolver · [#171](https://github.com/Gfermoto/BirdLense-Hub/issues/171) ✅ backfill/repair · [#172](https://github.com/Gfermoto/BirdLense-Hub/issues/172) ✅ background metadata jobs · [#173](https://github.com/Gfermoto/BirdLense-Hub/issues/173) ✅ observability + CI quality gate.
- Outcome (Mar 2026): production `processed=806`, `matched=806`, `unresolved=0` on startup; APIs `seed/backfill/unresolved/health/enrich`, async enrichment status, CI smoke for the registry.

---

## Shipped ideas (archive)

Historical **simple → complex** checklist (all rows shipped). Cross-check [FEATURES](./FEATURES.md); do **not** treat this table as a to-do list.

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
| ✅ Public gallery (opt-in) | [CONFIGURATION](./CONFIGURATION.md) → Gallery | High |
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

## Work order: finish in-flight work, then operator testing {#completion-then-operator-testing}

**Agreement:** first **complete** the agreed slice of work (open issues in the current wave / **BirdLense Hub — Roadmap** milestone: PR merged, issue **closed**, **`make deploy`** if needed, CI green). **Then** the operator runs **manual testing** on the live hub and files **feedback as new issues** (or flags regressions on an existing issue) — without growing the same wave in parallel.

**Backlog vs acceptance:** rows in **New ideas** without ✅ are **future queue**; only items **explicitly in progress** on the board count toward “ready for acceptance”. The **detection consilium** ([item 17](#detection-strategy-consilium)) runs **after** the current wave stabilizes unless the board decides otherwise.

---

## Near-term priorities (public)

| Priority | Focus |
|----------|--------|
| **Community** | [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions), `good first issue` triage, docs feedback |
| **Quality** | CI on PRs (UI build + MkDocs `--strict`), Dependabot / dependency hygiene |
| **Docs** | `VERSION` aligned with `mkdocs.yml`, `app/ui/package.json`, and `app/web/openapi.yaml` (`scripts/check-docs-version.py`); interactive OpenAPI (Redoc) on the doc site |
| **Releases** | Tags + GitHub Release → Docker semver image + Pages deploy |

The **shipped archive** above is historical only. Active work is the **consilium** issues and **future candidates**; always cross-check [FEATURES](./FEATURES.md).

---

## See also

[ACCESS_CONTROL](./ACCESS_CONTROL.md) · [DATASETS](./DATASETS.md) · [TESTING](./TESTING.md) · [CONFIGURATION](./CONFIGURATION.md)
