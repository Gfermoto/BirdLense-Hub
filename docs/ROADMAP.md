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

## Backlog (ideas)

Roughly ordered **simple → complex**. Many rows are **done** — kept for history; cross-check [FEATURES](./FEATURES.md) before assuming something is missing.

| Idea | Notes | Complexity |
|------|--------|--------------|
| Playback speed 0.5× / 2× | Video player | Low |
| Webhook on detection | JSON POST for automation | Low |
| CSV/JSON timeline export | Analytics | Low |
| “Last bird” Overview widget | | Low |
| Timeline time-of-day filter | | Low |
| PWA improvements | Install prompt, static cache | Low |
| Unknowns page | Low-confidence review | Medium |
| Monthly PDF report | | Medium |
| Xeno-canto on species page | | Medium |
| eBird export | | Medium |
| Prometheus / Grafana | `/metrics`, `/api/metrics` | Medium |
| Per-species confidence overrides | | Medium |
| iNaturalist crop export | | Medium |
| Web Push | | Medium |
| Public gallery (opt-in) | [CONFIGURATION](./CONFIGURATION.md) → Gallery | High |
| Migration calendar | Seasonal patterns | High |
| Region comparison (eBird) | Overview card | High |
| Sun/moon card on weather | | Low |

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
