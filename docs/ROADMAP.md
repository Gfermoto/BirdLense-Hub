# Roadmap — BirdLense Hub

Direction of travel and current stack. **Shipped items** are summarized here; details live in [Changelog](./project/changelog.md) and [FEATURES](./FEATURES.md).

[Русский](./ROADMAP.ru.md)

---

## Current stack (March 2026)

| Component | Version / note |
|-----------|----------------|
| **Ultralytics** | 8.4.21 (Docker base image) |
| **Platform** | x86/amd64 (**ARM not supported**) |
| **Detection** | `two_stage`: binary `.pt` + YOLO11n-cls (EU); `single_stage` fallback if weights missing |
| **EU classifier** | `best.pt` — birds-525 + iNaturalist (~491 species) |
| **US classifier** | `best_US.pt` — NABirds (fallback) |
| **React** | 19.2.4 |
| **Vite** | 6.4.1 |

---

## Recently delivered (high level)

- **Home Assistant** — MQTT discovery (e.g. last species, bird-detected). See [CONFIGURATION](./CONFIGURATION.md) → MQTT.
- **Dataset pipeline** — `best_frame` in YOLO layout, ZIP export (`GET /api/ui/dataset/export`), relabel moves on-disk crops. **System → Storage**.

---

## Backlog consilium (March 2026)

**Brainstorm roles:** product (operator value), security, platform/infra, ML & data, integrations (MQTT/HA/Frigate), UX, docs & OSS hygiene.

**Outcome:** triaged items are **GitHub Issues** (not shipped until closed in a release): [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46)–[#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57).

**Put them on the Project board:** OAuth scopes often loop on device login — use a **classic PAT** (`repo` + `project`) in `GH_TOKEN` or `scripts/.env.project` (see `scripts/env.project.example`), then:

```bash
bash scripts/github-project-add-backlog-consilium.sh
```

All open issues/PRs: `bash scripts/github-project-import-open-items.sh`. Or add cards manually in the GitHub UI.

| # | Theme | Issue | Labels (summary) |
|---|--------|-------|------------------|
| 1 | Rate limiting for settings / auth API | [#46](https://github.com/Gfermoto/BirdLense-Hub/issues/46) | `area:web`, P2 |
| 2 | Git history secret scan (maintainer) | [#47](https://github.com/Gfermoto/BirdLense-Hub/issues/47) | `area:infra`, docs |
| 3 | `export_birdlense_to_yolo.py` training export | [#48](https://github.com/Gfermoto/BirdLense-Hub/issues/48) | `area:processor`, P2 |
| 4 | ARM64 Docker spike | [#49](https://github.com/Gfermoto/BirdLense-Hub/issues/49) | `area:infra`, P3 |
| 5 | MQTT reconnect / missed-events clarity | [#50](https://github.com/Gfermoto/BirdLense-Hub/issues/50) | `area:processor`, P2 |
| 6 | UI: backup / restore SQLite | [#51](https://github.com/Gfermoto/BirdLense-Hub/issues/51) | `area:web`, P3 |
| 7 | UI i18n framework | [#52](https://github.com/Gfermoto/BirdLense-Hub/issues/52) | `area:web`, P3 |
| 8 | CI: scheduled image smoke test | [#53](https://github.com/Gfermoto/BirdLense-Hub/issues/53) | `area:infra`, P3 |
| 9 | CI: OpenAPI contract tests | [#54](https://github.com/Gfermoto/BirdLense-Hub/issues/54) | `area:web`, P3 |
| 10 | Yearly species checklist / life list | [#55](https://github.com/Gfermoto/BirdLense-Hub/issues/55) | `area:web`, P3 |
| 11 | CORS demo host → config/env | [#56](https://github.com/Gfermoto/BirdLense-Hub/issues/56) | `area:web`, P3 |
| 12 | Docs: Prometheus alert examples | [#57](https://github.com/Gfermoto/BirdLense-Hub/issues/57) | `area:docs`, P3 |

---

## Backlog (ideas)

Roughly ordered **simple → complex**. Many rows are **done** — kept for history; cross-check [FEATURES](./FEATURES.md) before assuming something is missing.

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

**Note:** This table is kept as a **shipped checklist** aligned with [ROADMAP.ru.md](./ROADMAP.ru.md) and the codebase. For **new** ideas, open a GitHub Discussion or Issue — do not assume a row here is still “to do”.

### UX backlog (selected)

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

The backlog table above mixes historical ideas with future work — always cross-check [FEATURES](./FEATURES.md) before starting.

---

## See also

[ACCESS_CONTROL](./ACCESS_CONTROL.md) · [DATASETS](./DATASETS.md) · [TESTING](./TESTING.md) · [CONFIGURATION](./CONFIGURATION.md)
