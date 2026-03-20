# Installation and Deployment — BirdLense Hub

BirdLense Hub — bird feeder monitoring: video and audio detection, recordings, analytics. Docker on x86.

**New here?** Read [OVERVIEW](./OVERVIEW.md) (what it is, who it’s for). **Recipes:** [SCENARIOS](./SCENARIOS.md).

[Русский](./INSTALL.ru.md)

## Requirements

| Component | Description |
|-----------|-------------|
| **Docker** | x86/amd64, Compose v2 |
| **Go2RTC** | Video streams from IP cameras (standalone or Frigate) |
| **MQTT** (optional) | Frigate events, BirdNET sightings |

---

## Option 1: Pre-built image (recommended)

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```

Image: `ghcr.io/gfermoto/birdlense-hub:latest`. UI: http://localhost:8085

## Option 2: Build from source

```bash
cd BirdLense-Hub/app
make build && make start
```

## Option 3: Image without repo (for users)

No cloning — image and config only:

```bash
mkdir -p birdlense-app && cd birdlense-app
mkdir -p data/recordings data/db app_config
# .env: PROCESSOR_SECRET, FLASK_SECRET_KEY (openssl rand -hex 16)
# docker-compose.image.yml from repo app/
docker compose -f docker-compose.image.yml up -d
```

Image: `ghcr.io/gfermoto/birdlense-hub:latest`. Files: `docker-compose.image.yml`, `.env`, `app_config/`, `data/`. Intel GPU: `cp docker-compose.intel.example.yml docker-compose.override.yml`.

---

## First run

1. **Secrets** — `make setup` creates `app/.env` (PROCESSOR_SECRET, FLASK_SECRET_KEY). Runs on `make start`/`make pull`.
2. **Config** — `app/app_config/user_config.yaml`. Examples: `cp configs/minimal.yaml app_config/user_config.yaml`.
3. **Go2RTC** — Settings → Video: URL (`http://IP:1984`).
4. **Cameras** — Settings → Cameras: stream names from Go2RTC.

---

## Deploy to server (make deploy)

```bash
cd BirdLense-Hub   # repo root (folder from git clone; rename OK)
make deploy
```

Requires: SSH (configure `~/.ssh/config` or `DEPLOY_HOST`), Docker on server, Node.js locally for UI build.

**Setup:** copy `scripts/deploy.local.sh.example` to `deploy.local.sh` and set `DEPLOY_HOST`, `DEPLOY_URL`, secrets; optional `DEPLOY_REMOTE_DIR`. File is gitignored.

**Remote directory:** `scripts/deploy.sh` defaults to `DEPLOY_REMOTE_DIR=/root/BirdLense` on the server. Your local clone folder (`BirdLense-Hub` or any name) does not need to match.

**What it does:** stops/removes container `birdlense`, builds UI locally, rsync (excludes `app/data`, `app/app_config/user_config.yaml`), merges secrets into `app/.env` on the server, Intel GPU override if `/dev/dri/renderD128` exists, `make build && make start` in `app/` on the server.

**Auto-deploy:** `./scripts/setup-auto-deploy.sh` on server → push to main → auto-deploy (self-hosted runner).

**Server unavailable:** `cd app && make build` locally; when access returns — `make deploy` (data untouched).

---

## Verification

- **Health:** `curl http://localhost:8085/api/ui/health`
- **Cameras:** Settings → Cameras
- **Live:** video stream with overlay

Recordings not visible? System → «Scan and import».

---

## Data

| Path | Contents |
|------|----------|
| `app/data/recordings/` | Video files (YYYY/MM/DD/HHMMSS/video.mp4) |
| `app/data/db/birdlense.db` | SQLite |
| `app/app_config/user_config.yaml` | User config |

---

See also: [CONFIGURATION](./CONFIGURATION.md) · [SCENARIOS](./SCENARIOS.md) · [GLOSSARY](./GLOSSARY.md) · [TROUBLESHOOTING](./TROUBLESHOOTING.md) · [Security policy](./project/security-policy.md).
