# Installation and Deployment — BirdLense Hub

BirdLense Hub — bird feeder monitoring: video and audio detection, recordings, analytics. Docker on **x86_64** (Intel or AMD).

**New here?** Read [OVERVIEW](./OVERVIEW.md) (what it is, who it’s for). **Recipes:** [SCENARIOS](./SCENARIOS.md).

[Русский](./INSTALL.ru.md)

## Requirements

| Component | Description |
|-----------|-------------|
| **Docker** | **x86_64 / amd64** (Intel or AMD), Compose v2 — ARM/aarch64 not supported |
| **Go2RTC** | Video streams from IP cameras (standalone or Frigate) |
| **MQTT** (optional) | Frigate events; BirdNET (any compatible JSON publisher, often BirdNET-Go or BirdNET-Pi) |

---

## Option 1: One-step Docker install

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub
./install.sh
```

The script checks Docker, installs it if needed, creates `app/.env`, and starts the stack.

## Option 2: Pre-built image (recommended)

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```

Image: `ghcr.io/gfermoto/birdlense-hub:latest`. UI: http://localhost:8085

## Option 3: Build from source

```bash
cd BirdLense-Hub/app
make build && make start
```

## Option 4: Image without repo (for users)

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

**Docker volumes and uid:** container processes run as **`birdlense` (uid 1000)**. The entrypoint briefly runs as root to `chown` bind-mounted `./data` and `./app_config`. If `chown` is not allowed on your filesystem, from the host under `app/`: `chown -R 1000:1000 data app_config`.

1. **Secrets** — `make setup` creates `app/.env` (PROCESSOR_SECRET, FLASK_SECRET_KEY). Runs on `make start`/`make pull`, and from `./install.sh`.
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

**What it does:** stops/removes container `birdlense`, builds UI locally, rsync (excludes `app/data`, `app/app_config/user_config.yaml`, `.tools/` for local CodeQL, venvs, `site/`), merges secrets into `app/.env` on the server (`MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET`, optional **`BIRDLENSE_STRICT_API_AUTH`** / **`BIRDLENSE_UI_API_KEY`** — see [CONFIGURATION.md](./CONFIGURATION.md), [SECRETS_ROTATION.md](./SECRETS_ROTATION.md)), Intel GPU override if `/dev/dri/renderD128` exists, `make build && make start` in `app/` on the server.

**Auto-deploy:** `./scripts/setup-auto-deploy.sh` on server → push to main → GitHub Actions workflow **Deploy** (self-hosted runner with labels `self-hosted`, `birdlense`). If the run stays **Queued**, the runner is offline or not registered — use **`make deploy`** from your machine until the runner is fixed.

**Server unavailable:** `cd app && make build` locally; when access returns — `make deploy` (data untouched).

**Linear checklist**, VPS paths, logs, common pitfalls: [DEPLOY_SERVER](./DEPLOY_SERVER.md).

### Telegram proxy autorotate (one command)

After the first successful `make deploy` (so scripts are present on the server):

```bash
cd BirdLense-Hub
make proxy-rotation-install
```

Done: a server cron job will rotate Telegram SOCKS5 proxy every 6 hours and apply changes only when the best proxy actually changes.

Useful commands:

```bash
make proxy-rotation-status   # show schedule and recent logs
make proxy-rotation-remove   # disable autorotate
make refresh-telegram-proxy  # one-shot proxy selection now
```

If `status` shows `not installed`, verify `scripts/deploy.local.sh` (`DEPLOY_HOST` / `DEPLOY_SSH_PORT`) and run install again.

---

## Verification

- **Health:** `curl http://localhost:8085/api/ui/health`
- **Cameras:** Settings → Cameras
- **Live:** video stream with overlay
- **DB backup:** System → Storage → “Download DB backup”

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
