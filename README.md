<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

[![Version](https://img.shields.io/badge/version-0.3.5-blue.svg)](./CHANGELOG.md) [Русский](./README.ru.md) · [Contributing](./CONTRIBUTING.md) [RU](./CONTRIBUTING.ru.md) · [Security](./SECURITY.md) [RU](./SECURITY.ru.md)

### Short description

Canonical one-liners for **GitHub About**, mirrors, and press: **[SHORT_DESCRIPTION.md](./SHORT_DESCRIPTION.md)** · **[SHORT_DESCRIPTION.ru.md](./SHORT_DESCRIPTION.ru.md)**

Bird monitoring for feeders, gardens, and field setups: computer vision and audio recognition to detect, identify, record, and analyze visits—aimed at ornithology, citizen science, and operators who keep data on their own hardware. Runs in Docker on x86; integrates with Go2RTC, Frigate, BirdNET via MQTT. No vendor cloud required for core processing.

**Docs:** [Project overview](./docs/OVERVIEW.md) · [Full documentation index](./docs/README.md) · [Documentation site (Pages)](https://gfermoto.github.io/BirdLense-Hub/)

**Community:** [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions) · [Issues](https://github.com/Gfermoto/BirdLense-Hub/issues)

### Model info

Two components: **detector** (bird or rodent in frame) and **classifier** (bird species).

| Component | Version | Trained on | Note |
|-----------|---------|------------|------|
| **Detector** | YOLO11n | NABirds + COCO birds + OIDv4 squirrel | Binary bird/rodent (weights may still name the rodent class “squirrel”; hub maps to Rodent) — unchanged in EU training |
| **Classifier** | YOLO11n-cls | birds-525 + iNaturalist (≈490) | EU default; US/NABirds is optional backup |

**Current model:** EU (birds-525 + iNaturalist Europe, ~491 species). US (NABirds) — backup in `best_US.pt`.

**EU model:** classifier trained on merged_cls → [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged). Weights: [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu). Training: [docs/TRAINING.md](./docs/TRAINING.md). Detector unchanged.

**Runtime weights:** two-stage `app/processor/models/detection/weights/best.pt` (binary from zip in fork [AleksandrRogachev94/BirdLense `app/processor`](https://github.com/AleksandrRogachev94/BirdLense/tree/main/app/processor)) and `app/processor/models/classification/weights/best.pt` ([`gfermoto/birdlense-birds-eu`](https://huggingface.co/gfermoto/birdlense-birds-eu) on Hugging Face). `scripts/fetch-processor-weights.sh` fetches both. Keep `class_names.txt` aligned with the classifier. `app/yolo11n.pt` is legacy-only (`--legacy-single-stage`).

**Catalog hygiene:** align the Hub species list with your classifier using `species.catalog_allowlist_file` + optional `catalog_strict_ingest`, `scripts/datasets/dump_classifier_allowlist.py`, and `POST /api/ui/system/species-catalog/reconcile` — see [docs/CONFIGURATION.md](./docs/CONFIGURATION.md).

<details>
<summary>📷 Screenshots</summary>
<br>
<p align="center">
  <img src="screenshots/dashboard1.jpg" width="800" alt="Dashboard">
</p>
<p align="center">
  <img src="screenshots/dashboard2.jpg" width="800" alt="Activity">
</p>
<p align="center">
  <img src="screenshots/video-details.jpg" width="800" alt="Video Details">
</p>
</details>

## Features

### Core
- **Live video** — streaming from IP cameras via [Go2RTC](https://github.com/AlexxIT/Go2RTC), real-time detection overlays
- **Bird detection** — custom YOLO + ByteTrack tracking, two-stage strategy (binary detector + species classifier)
- **Audio** — [BirdNET](https://github.com/kahst/BirdNET-Analyzer) sightings via MQTT (BirdNET-Pi/Go)
- **Triggers** — OpenCV motion, Frigate events, MQTT binary, ESPHome
- **Timeline** — date + time-of-day filter (Morning, Day, Evening, Night 22–06), video playback, spectrograms, track visualization
- **UI** — React 19, Material UI, i18n (en/ru/zh), mobile-friendly, PWA (install prompt, offline cache)
- **Weather** — OpenWeather or Home Assistant
- **Notifications** — Telegram Bot API
- **MCP** — optional [Model Context Protocol](https://modelcontextprotocol.io/) for **authorized clients** (automation, integrations; see `docs/MCP_SETUP.md`)

### Analytics & Export
- **CSV/JSON export** — download visits for analysis in Excel/Python
- **eBird export** — checklist format for import into eBird.org
- **Region comparison** — compare your species with eBird region top (Overview card)
- **PDF report** — monthly summary: species count, top-5, charts
- **Prometheus metrics** — `/metrics` for Grafana dashboards

### Citizen Science
- **iNaturalist** — one-click export: download crop from video, open inaturalist.org/observations/upload
- **Unknowns** — low-confidence detections for manual review; date + time-of-day filter (like Timeline)

### Integrations
- **Webhook** — POST on each detection (IFTTT, Zapier)
- **Bird song player** — Xeno-canto recordings on species page
- **Confidence per species** — lower threshold for rare birds
- **Research** — dataset collection, model fine-tuning (see [docs](./docs))

## Quick Start

**Docker (free image):**
```bash
docker pull ghcr.io/gfermoto/birdlense-hub:latest
# or use docker-compose — see docs/INSTALL.md
```
UI: http://localhost:8085

**Quickstart:** [docs/QUICKSTART.md](./docs/QUICKSTART.md) | **Full install:** [docs/INSTALL.md](./docs/INSTALL.md) | **Scenarios:** [docs/SCENARIOS.md](./docs/SCENARIOS.md) | **All docs:** [docs/README.md](./docs/README.md) | **Features:** [docs/FEATURES.md](./docs/FEATURES.md)

For a one-step Docker bootstrap, run `./install.sh` from the repository root. It installs Docker if needed, creates `app/.env`, starts the stack, and verifies the shared `health + readiness + status` contract.

## Developers

- **Local setup:** [docs/LOCAL_DEV.md](./docs/LOCAL_DEV.md) — Docker, **Node.js 22** for `app/ui` (see `app/ui/.nvmrc` and `package.json` `engines`), MkDocs venv vs app Python.
- **Tests & CI:** [docs/TESTING.md](./docs/TESTING.md) — `make test`, `make test-web`, E2E; processor tests are RAM-heavy.
- **Contributing:** [CONTRIBUTING.md](./CONTRIBUTING.md).

### First-time contributor CI (same as Actions)

1. **Node.js ≥ 22** (see `app/ui/package.json` `engines` and `app/ui/.nvmrc`).
2. From repo root run **`make ci-local`** — it creates **`.venv-ci`** if missing and executes [`scripts/ci-full-local.sh`](./scripts/ci-full-local.sh) (single source of truth for [`.github/workflows/ci-pr.yml`](./.github/workflows/ci-pr.yml)).
3. Web pytest only (matches CI `PYTHONPATH`):

```bash
cd app && PYTHONPATH="${PWD}:${PWD}/web" ../.venv-ci/bin/python -m pytest web/tests/ -q --tb=short
```

**UI map (where to click):** [docs/UI_SETTINGS_MAP.md](./docs/UI_SETTINGS_MAP.md) · [RU](./docs/UI_SETTINGS_MAP.ru.md)
- **Weights workflow:** `scripts/fetch-processor-weights.sh` prefers the two-stage detector/classifier paths; use `--legacy-single-stage` only if you explicitly need the compatibility `app/yolo11n.pt` asset from GitHub Release `weights/v1`.

## Requirements

- **Docker** — x86/amd64
- **Go2RTC** — video streams (standalone or in Frigate), e.g. `http://YOUR_HOST:1984`
- **MQTT** (optional) — Frigate events, BirdNET sightings

## Structure

| Path | Description |
|------|-------------|
| [app/](./app) | Application (UI, API, processor) — single container |
| [docs/](./docs) | Architecture, config, API, deployment, MCP |
| [scripts/](./scripts) | Deploy, restore-config, datasets, verification |

## Commands

From repo root:

| Command | Description |
|---------|-------------|
| `make deploy` | Deploy to server (requires `scripts/deploy.local.sh`) |
| `make verify` | Check `health` + `readiness` + `status` on `BASE_URL` or localhost |
| `make ci-local` | Run `scripts/ci-full-local.sh` — Bandit, pip-audit, Ruff, full `web/tests` pytest, docs version, UI (codegen + Vitest + typecheck + lint + build), Settings UI coverage, MkDocs strict (see [docs/CI_AND_QUALITY.md](./docs/CI_AND_QUALITY.md)) |
| `make ci-local-docker` | Same as `ci-local`, then Docker image tests + Playwright smoke (heavy; needs processor weights) |
| `make build` | Build Docker image |
| `make start` | Start container |
| `make stop` | Stop container |
| `make logs` | View logs |

**Release gate (short):** [Definition of Done](./docs/DEFINITION_OF_DONE.md) · [RU](./docs/DEFINITION_OF_DONE.ru.md) — `make ci-local`, `verify-stack`, 5-minute smoke. Full checklist: [RELEASE_READINESS](./docs/RELEASE_READINESS.md).

From `app/`:

| Command | Description |
|---------|-------------|
| `make pull` | Pull and run pre-built image |
| `make setup` | Create `.env` with secrets (runs automatically) |

## Configuration

- **Settings** → Video: Go2RTC URL (`http://IP:1984`)
- **Settings** → Cameras: stream names from Go2RTC
- **Settings** → MQTT: broker for Frigate/BirdNET
- Config file: `app/app_config/user_config.yaml`

## Security

For production, set in `app/.env` (or via `deploy.local.sh` when deploying):

| Variable | Purpose |
|----------|---------|
| `FLASK_SECRET_KEY` | Flask session (settings protection) |
| `PROCESSOR_SECRET` | Processor API protection (`X-Processor-Token` header) |
| `BIRDLENSE_ENV` | `production` — strict secret validation |

Secrets are auto-generated on first `make start` or `make pull`. See `app/.env.example`. Deploy script writes them to server `app/.env`.

## License

See [LICENSE](LICENSE). Docker image: CC BY-NC-ND 4.0 for non-commercial use.

## Acknowledgments

- [BirdLense](https://github.com/AleksandrRogachev94/BirdLense) by Aleksandr Rogachev — inspired the creation of this project
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- [BirdNET-Analyzer](https://github.com/kahst/BirdNET-Analyzer)
- [NABirds](https://dl.allaboutbirds.org/nabirds), [COCO](https://cocodataset.org/), [Open Images](https://storage.googleapis.com/openimages/web/index.html) (OIDv4 squirrel) — detector
- [34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species), [iNaturalist](https://www.inaturalist.org/) (Europe) — classifier (merged)
- [Material-UI](https://mui.com/)
- [OpenWeatherMap](https://openweathermap.org/)
