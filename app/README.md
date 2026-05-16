# BirdLense Hub

[Русский](./README.ru.md)

Single container. Connects to Go2RTC (standalone or via Frigate) and MQTT (BirdNET, Frigate).

**Features:** Timeline (date + time of day), CSV/JSON/eBird export, PDF report, “Unknowns”, iNaturalist, Xeno-canto, Prometheus. See [docs/user/features.md](../docs/user/features.md).

## Run

### Local development (no remote server)

```bash
cd app
make local
```

See [docs/contributor/local-dev.md](../docs/contributor/local-dev.md) — full build, tests, E2E.

### Option 1: Pre-built image (recommended)

```bash
cd app
make pull
```

Image: `ghcr.io/gfermoto/birdlense-hub:latest` ([GitHub Packages](https://github.com/Gfermoto/BirdLense-Hub/pkgs/container/birdlense-hub))

### Option 2: Build from source

```bash
cd app
make build && make start
```

UI: http://localhost:8085

## Commands

| Command | Description |
|---------|-------------|
| `make setup` | Create `app/.env` with `PROCESSOR_SECRET` and `FLASK_SECRET_KEY` (runs automatically) |
| `make build` | Build image |
| `make start` | Start (after build) |
| `make pull` | Pull and run pre-built image |
| `make stop` | Stop |
| `make logs` | Logs |
| `make deploy` | Deploy to server (from repo root; see [docs/user/install.md](../docs/user/install.md)) |

## Configuration

- `app_config/default_config.yaml` — defaults shipped with the image/repo (read-only baseline).
- `app_config/user_config.yaml` — **operator overrides**: deep-merged over default; this file is the primary place for durable settings in the UI. Server deploy does not rsync over your live `data/` or `user_config.yaml` (see [docs/user/install.md](../docs/user/install.md) / deploy rules).
- **Environment variables** — runtime layer for secrets, infra, and flags: e.g. `DATA_DIR`, `MQTT_BROKER`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `GO2RTC_URL`, `PROCESSOR_SECRET`, `FLASK_SECRET_KEY`, `BIRDLENSE_*`, `MCP_TOKEN`. Many code paths use **env first, then YAML** (e.g. MQTT broker in processor bootstrap and some UI checks).
- On load, merged config is checked for **top-level section types** (each known section must be a mapping, not a scalar). Errors are logged; set `BIRDLENSE_STRICT_CONFIG=1` to **fail fast** at startup if validation fails.

- **Go2RTC URL:** Settings → Video — `http://IP:1984` (host where Go2RTC is reachable)
- Cameras: Settings → Cameras (stream name from Go2RTC)
- Examples: `cp configs/minimal.yaml app_config/user_config.yaml`

## Data

- `./data/recordings/` — videos (`YYYY/MM/DD/HHMMSS/video.mp4`)
- `./data/db/birdlense.db` — SQLite
- `./app_config/` — config

No recordings in UI? System → “Scan and import”.

## MCP

Settings → section 8. Setup: [docs/contributor/mcp-setup.md](../docs/contributor/mcp-setup.md)

## Deploy

```bash
cd BirdLense
make deploy
```

Syncs code to the server (see `scripts/deploy.local.sh.example`), **does not touch** server `data/`.

## Requirements

- Go2RTC — set host in Settings (`http://IP:1984`)
- MQTT (optional)
