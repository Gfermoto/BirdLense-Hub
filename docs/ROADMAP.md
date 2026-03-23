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
- **Public gallery (opt-in)** — [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) closed (v0.2.4): background upload runs inside **Flask app context**; troubleshooting in [CONFIGURATION](./CONFIGURATION.md) → Gallery.

---

## Backlog consilium (March 2026)

**Brainstorm roles:** product (operator value), security, platform/infra, ML & data, integrations (MQTT/HA/Frigate), UX, docs & OSS hygiene.

**Outcome:** triaged items are **GitHub Issues** (not shipped until closed in a release): [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48), [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57), [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) (operator UX — Mar 2026; phase B: Unknowns snackbar **Open video**). **Done:** [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) (git-history secret scan + SECURITY updates), [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) (`export_birdlense_to_yolo.py`), [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) (gallery upload thread app context, v0.2.4), [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) (same-UTC-day video prev/next, v0.2.6), [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) (local TZ / cross-day / docs). [#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) (ARM Docker) is **closed** — x86-only; not part of this backlog.

**Put them on the Project board:** OAuth scopes often loop on device login — use a **classic PAT** (`repo` + `project`) in `GH_TOKEN` or `scripts/.env.project` (see `scripts/env.project.example`), then:

```bash
bash scripts/github-project-add-backlog-consilium.sh
```

All open issues/PRs: `bash scripts/github-project-import-open-items.sh`. Or add cards manually in the GitHub UI.

| # | Theme | Issue | Labels (summary) |
|---|--------|-------|------------------|
| 1 | Rate limiting for settings / auth API | [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46) ✅ `verify-password`, docs, tests | `area:web`, P2 |
| 2 | Git history secret scan (maintainer) | [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) ✅ gitleaks script + SECURITY EN/RU | `area:infra`, P3, `documentation` |
| 3 | `export_birdlense_to_yolo.py` training export | [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) ✅ YOLO cls `train/val` export script | `area:processor`, P2 |
| 4 | MQTT reconnect / missed-events clarity | [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) | `area:processor`, P2 |
| 5 | UI: backup / restore SQLite | [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) | `area:web`, P3 |
| 6 | UI i18n framework | [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) | `area:web`, P3 |
| 7 | CI: scheduled image smoke test | [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) | `area:infra`, P3 |
| 8 | CI: OpenAPI contract tests | [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) | `area:web`, P3 |
| 9 | Yearly species checklist / life list | [#55](https://github.com/Gfermoto/BirdLense-Hub/issues/55) | `area:web`, P3 |
| 10 | CORS demo host → config/env | [#56](https://github.com/Gfermoto/BirdLense-Hub/issues/56) | `area:web`, P3 |
| 11 | Docs: Prometheus alert examples | [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) ✅ `examples/prometheus/`, [CONFIGURATION](./CONFIGURATION.md) | `area:docs`, P3 |
| 12 | Gallery: investigate / fix (opt-in public gallery) | [#80](https://github.com/Gfermoto/BirdLense-Hub/issues/80) ✅ app context in upload thread + docs/tests v0.2.4 | `area:web`, P2, `bug` |
| 13 | Manual species correction: unify Unknowns vs in-video flow | [#81](https://github.com/Gfermoto/BirdLense-Hub/issues/81) 📝 Phases A + B in **v0.2.5** (Unknowns snackbar **Open video**); phase C on demand | `area:web`, P2 |
| 14 | Video navigation: sequential browse (e.g. same day), no list reset | [#82](https://github.com/Gfermoto/BirdLense-Hub/issues/82) ✅ UI + `GET /videos/:id/neighbors` **v0.2.6** | `area:web`, P2 |
| 15 | Video neighbors: local TZ, cross-day jump, docs clarity (follow-up to #82) | [#85](https://github.com/Gfermoto/BirdLense-Hub/issues/85) ✅ local day + `cross_day` + API/UI docs | `area:web`, P3 |

### Triage: Issue vs. Discussion

| Use | When |
|-----|------|
| **[GitHub Issue](https://github.com/Gfermoto/BirdLense-Hub/issues)** | Clear scope, definition of done, fits an area label (`area:*`) and priority — work can land on the **Project** board. |
| **[Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** | Exploratory ideas, multiple design options, “should we at all?”, community input before committing. |

**After consilium:** new tracked work → create/update the Issue, add the card to the Project (`github-project-add-backlog-consilium.sh` or manually), then **update this ROADMAP** table in the same PR or follow-up.

**Reporting (all shipped work, not only consilium):** every shipped item has a **GitHub Issue** (open one if missing) and, when tracked, a card on **BirdLense Hub — Roadmap**. When done: comment (outcome + PR links), **close** the issue, set board **Status → Done** (with a PAT: `bash scripts/github-project-mark-done.sh <n>`). Checklist: root **[CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md)** § *Issues & Project board*.

---

## Future work candidates (no issue yet)

Themes worth **Issues** when you are ready to schedule them (not on the consilium board today):

| Theme | Why |
|-------|-----|
| **Accessibility (a11y)** | Keyboard navigation, focus order, contrast — natural follow-up after UI i18n ([#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52)). |
| **Broader E2E (Playwright)** | Beyond smoke: login, timeline, critical settings — tied to CI cost and flake budget. |
| **Secrets in production** | Documented rotation / operational path for `secrets.*` and related keys (complements maintainer git scan [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47)). |
| **Stack version sync** | After bumping Ultralytics, React, or base image — align **this doc**, `Dockerfile`, and release notes in one pass. |
| **Community / donation UX** | Leaderboards, supporter badges, etc. — exploratory; `general.donate_url` already exists — [CONFIGURATION](./CONFIGURATION.md). |

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

## Near-term priorities (public)

| Priority | Focus |
|----------|--------|
| **Community** | [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions), `good first issue` triage, docs feedback |
| **Quality** | CI on PRs (UI build + MkDocs `--strict`), Dependabot / dependency hygiene |
| **Docs** | Version banner in `mkdocs.yml` matches `VERSION`; interactive OpenAPI (Redoc) on the doc site |
| **Releases** | Tags + GitHub Release → Docker semver image + Pages deploy |

The **shipped archive** above is historical only. Active work is the **consilium** issues and **future candidates**; always cross-check [FEATURES](./FEATURES.md).

---

## See also

[ACCESS_CONTROL](./ACCESS_CONTROL.md) · [DATASETS](./DATASETS.md) · [TESTING](./TESTING.md) · [CONFIGURATION](./CONFIGURATION.md)
