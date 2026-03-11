<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

[Русский](./README.ru.md)

Smart bird feeder monitoring: computer vision and audio recognition to detect, identify, record, and analyze birds. Runs in Docker on x86, integrates with Go2RTC, Frigate, BirdNET via MQTT. No cloud — fully local.

**Research tool:** dataset collection from live recordings, YOLO training scripts (NABirds, COCO), model fine-tuning notebooks. See [docs/DATASET_TRAINING_PLAN.md](./docs/DATASET_TRAINING_PLAN.md).

### Model info

| Component | Version | Trained on | Note |
|-----------|---------|------------|------|
| **Detector** | YOLOv8n (Ultralytics 8.4.21) | NABirds + COCO birds + OIDv4 squirrel | Binary bird/squirrel |
| **Classifier** | YOLOv8n-cls | NABirds (~400 species) | **Mainly North American birds** |

**Planned:** retrain on YOLO11n (see [UPGRADE_PLAN.md](./docs/UPGRADE_PLAN.md)).

**Training pipeline:** 1) **Pretrain** on open datasets (NABirds, birds-525-species, Birdsnap, CUB-200, iNaturalist) → 2) **Fine-tune** on BirdLense recordings from feeders. See [docs/FINETUNE_OPEN_DATASETS.md](./docs/FINETUNE_OPEN_DATASETS.md).

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

- **Live video** — streaming from IP cameras via [Go2RTC](https://github.com/AlexxIT/Go2RTC), real-time detection overlays
- **Bird detection** — custom YOLO + ByteTrack tracking, two-stage strategy (binary detector + species classifier)
- **Audio** — [BirdNET](https://github.com/kahst/BirdNET-Analyzer) sightings via MQTT (BirdNET-Pi/Go)
- **Triggers** — OpenCV motion, Frigate events, MQTT binary, ESPHome
- **Timeline** — video playback, spectrograms, track visualization, species visits
- **UI** — React, Material UI, i18n (en/ru), mobile-friendly
- **Weather** — OpenWeather or Home Assistant
- **Notifications** — [ntfy](https://ntfy.sh)
- **MCP** — Model Context Protocol for external tools
- **Research** — dataset prep (NABirds, COCO → YOLO), training notebooks, export pipeline for model fine-tuning

## Quick Start

**Local (Docker):**
```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```
UI: http://localhost:8085

**Deploy to server:** `make deploy` from repo root. Details: [app/README.md](./app/README.md)

On first run, `make setup` creates `app/.env` with `PROCESSOR_SECRET` and `FLASK_SECRET_KEY` automatically.

## Requirements

- **Docker** — x86/amd64
- **Go2RTC** — video streams (standalone or in Frigate), `http://IP:1984`
- **MQTT** (optional) — Frigate events, BirdNET sightings

## Structure

| Path | Description |
|------|-------------|
| [app/](./app) | Application (UI, API, processor) — single container |
| [docs/](./docs) | Architecture, config, API, deployment, MCP, **dataset & training plan** |
| [scripts/](./scripts) | Deploy, **datasets** (NABirds/COCO→YOLO), **training** notebooks |

**Research scripts:** `scripts/datasets/` — dataset conversion; `scripts/birds_train*.ipynb` — model training. Full inventory: [docs/DATASET_SCRIPTS.md](./docs/DATASET_SCRIPTS.md).

## Commands

From repo root:

| Command | Description |
|---------|-------------|
| `make deploy` | Deploy to server (see [.cursor/rules/deploy.mdc](.cursor/rules/deploy.mdc)) |
| `make build` | Build Docker image |
| `make start` | Start container |
| `make stop` | Stop container |
| `make logs` | View logs |

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

For production, set in `app/.env`:

| Variable | Purpose |
|----------|---------|
| `FLASK_SECRET_KEY` | Flask session (settings protection) |
| `PROCESSOR_SECRET` | Processor API protection (`X-Processor-Token` header) |

Secrets are auto-generated on first `make start` or `make pull`. See `app/.env.example`.

## License

CC BY-NC-ND 4.0 — see [LICENSE](LICENSE).

## Acknowledgments

- [BirdLense](https://github.com/AleksandrRogachev94/BirdLense) by Aleksandr Rogachev — inspired the creation of this project
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- [BirdNET-Analyzer](https://github.com/kahst/BirdNET-Analyzer)
- [NABirds](https://dl.allaboutbirds.org/nabirds)
- [Material-UI](https://mui.com/)
- [OpenWeatherMap](https://openweathermap.org/)
