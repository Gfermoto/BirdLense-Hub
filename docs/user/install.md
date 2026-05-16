# Installation and Deployment — BirdLense Hub

BirdLense Hub — bird feeder monitoring: video and audio detection, recordings, analytics. Docker on **x86_64** (Intel or AMD).

**New here?** Read [OVERVIEW](./overview.md) (what it is, who it’s for). **Recipes:** [SCENARIOS](./scenarios.md).

[Русский](../ru/install.ru.md)

## Requirements

| Component | Description |
|-----------|-------------|
| **Docker** | **x86_64 / amd64** (Intel or AMD), Compose v2 — ARM/aarch64 not supported |
| **Go2RTC** | Video streams from IP cameras (standalone or Frigate) |
| **MQTT** (optional) | Frigate events; BirdNET (any compatible JSON publisher, often BirdNET-Go or BirdNET-Pi) |

---

## Option 1: One-step Docker install (recommended)

From the **repository root** — **no `make` required** for bootstrap:

```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub
./install.sh
```

The script checks Docker, installs it if needed, runs `app/scripts/setup-env.sh` (creates `app/.env` with secrets), builds and starts the stack, then runs **`scripts/verify-stack.sh`** (health, readiness, status).

**Pre-built image** (skip local `docker compose build`):

```bash
./install.sh --pull
```

Same as `make install` / `make install-pull` from the repo root.

Image: `ghcr.io/gfermoto/birdlense-hub:latest`. UI: `http://127.0.0.1:8085` (or `BIRDLENSE_PORT`).

## Option 2: Make-only (same as Option 1)

```bash
cd BirdLense-Hub
make install          # build locally
# or
make install-pull     # ghcr image
```

Equivalent to `./install.sh` / `./install.sh --pull`.

## Option 3: Build from source

```bash
cd BirdLense-Hub/app
make build && make start
```

Then verify from the repository root:

```bash
cd ..
make verify
```

## Option 4: Image without repo (for users)

No cloning — image and config only (**one** `birdlense` service in `docker-compose.image.yml`). A full **git checkout** uses **`app/docker-compose.yml`**, which also starts **Redis** (`birdlense-redis`) for the default `REDIS_URL`; this minimal recipe does **not**:

```bash
mkdir -p birdlense-app && cd birdlense-app
mkdir -p data/recordings data/db app_config
# Download `app/docker-compose.image.yml` and `app/.env.example` from the repo, then:
cp .env.example .env
# Fill .env: PROCESSOR_SECRET, FLASK_SECRET_KEY (e.g. openssl rand -hex 16).
# Optional: BIRDLENSE_IMAGE=… for a custom registry (see docker-compose.image.yml).
docker compose -f docker-compose.image.yml up -d
```

Image: `ghcr.io/gfermoto/birdlense-hub:latest`. Files: `docker-compose.image.yml`, `.env`, `app_config/`, `data/`. **Intel GPU:** from `app/` run `bash scripts/docker-compose-intel-override-gen.sh` (all `card*`/`renderD*`, host `group_add` for video/render, `CAP_PERFMON`) or edit `docker-compose.intel.example.yml` manually (set GIDs). If logs show **`Failed to initialize PMU`** while `PERFMON` is already in compose, lower **`kernel.perf_event_paranoid` on the host** (not in the container): `make deploy` and CI write **`/etc/sysctl.d/99-birdlense-perf.conf`** with **0** when `docker-compose.override.yml` exists (many VPS images default to **3**). If **0** is not enough, try **`sudo sysctl kernel.perf_event_paranoid=-1`** or add **`privileged: true`** to the Intel override.

---

Verify:

```bash
curl -s http://127.0.0.1:8085/api/ui/health
curl -s http://127.0.0.1:8085/api/ui/readiness
curl -s http://127.0.0.1:8085/api/ui/status
```

## First run

**Docker volumes and uid:** container processes run as **`birdlense` (uid 1000)**. The entrypoint briefly runs as root to `chown` bind-mounted `./data` and `./app_config`. If `chown` is not allowed on your filesystem, from the host under `app/`: `chown -R 1000:1000 data app_config`.

1. **Secrets** — `app/scripts/setup-env.sh` creates `app/.env` (PROCESSOR_SECRET, FLASK_SECRET_KEY). `./install.sh` calls it directly; `make setup` / `make start` / `make pull` also use it.
2. **Config** — `app/app_config/user_config.yaml`. Example from the repo **`app/`** directory: `cp configs/minimal.yaml app_config/user_config.yaml`.
3. **Go2RTC** — Settings → Video: URL (`http://IP:1984`).
4. **Cameras** — Settings → Cameras: stream names from Go2RTC.

---

## Deploy to server (make deploy)

```bash
cd BirdLense-Hub   # repo root (folder from git clone; rename OK)
make deploy
```

Requires: SSH (configure `~/.ssh/config` or `DEPLOY_HOST` / optional **`DEPLOY_SSH_PORT`**), Docker on server, **Node.js 22 + npm 10+ locally** — `scripts/deploy.sh` runs **`npm ci && npm run build`** in `app/ui` on your machine before rsync (avoids npm timeouts on the server).

**Setup:** copy `scripts/deploy.local.sh.example` to `deploy.local.sh` and set `DEPLOY_HOST`, `DEPLOY_URL`, secrets; optional `DEPLOY_REMOTE_DIR`. File is gitignored.

**Remote directory:** `scripts/deploy.sh` defaults to `DEPLOY_REMOTE_DIR=/root/BirdLense` on the server. Your local clone folder (`BirdLense-Hub` or any name) does not need to match.

**What it does:** stops/removes container **`birdlense`** (leaves **`birdlense-redis`** if present), runs **local** UI `npm ci && npm run build`, **rsync** with excludes aligned to `scripts/deploy.sh` (among others: **`datasets/`**, **`app/data/`**, **`app/.env`**, **`app/app_config/user_config.yaml`**, **`.tools/`**, **`.venv-ci`** / **`.venv-docs`**, `app/.venv`, `site/`, `node_modules`, ruff/pytest caches), merges secrets into **`app/.env`** on the server (`MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET`, optional **`BIRDLENSE_STRICT_API_AUTH`** / **`BIRDLENSE_UI_API_KEY`** — see [CONFIGURATION.md](./configuration.md), [SECRETS_ROTATION.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/SECRETS_ROTATION.md)), if `/dev/dri/renderD*` exists runs **`bash scripts/docker-compose-intel-override-gen.sh`** (VA-API + GPU metrics), **`make build && make start`** in `app/` on the server, then **`scripts/verify-stack.sh`** against **`DEPLOY_URL`** (health, readiness, status, cameras when reachable).

**Auto-deploy:** `./scripts/setup-auto-deploy.sh` on server → push to main → GitHub Actions workflow **Deploy** (self-hosted runner with labels `self-hosted`, `birdlense`). If the run stays **Queued**, the runner is offline or not registered — use **`make deploy`** from your machine until the runner is fixed.

**Server unavailable:** `cd app && make build` locally; when access returns — `make deploy` (data untouched).

**Linear checklist**, VPS paths, logs, common pitfalls: [DEPLOY_SERVER](./deploy-server.md).

### HTTPS / nginx and large uploads (Library → file replay)

If uploads return **413** while the UI still shows an old hub limit (e.g. 2048 MiB), the server may be on stale config **or** a **proxy** rejects the body before Flask. The hub image sets a high Flask **`MAX_CONTENT_LENGTH`** (override with **`FLASK_MAX_CONTENT_LENGTH`** bytes in the environment). Nginx **inside** the Hub container already sets **`client_max_body_size 64g`** (`app/nginx/docker-nginx-main.conf`). If you terminate TLS or run another reverse proxy **in front of** the container, raise the limit there too, e.g.:

```nginx
location /api/ {
    client_max_body_size 16g;
    proxy_pass http://127.0.0.1:8085;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Tune **`client_max_body_size`** to your clips; YAML key **`video.file_test_max_upload_mb`** (repo default **10240** MiB after update).

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

- **Shared contract:** `make verify`
- **Health:** `curl http://localhost:8085/api/ui/health`
- **Readiness:** `curl http://localhost:8085/api/ui/readiness`
- **Status:** `curl http://localhost:8085/api/ui/status`
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

See also: [CONFIGURATION](./configuration.md) · [SCENARIOS](./scenarios.md) · [GLOSSARY](./glossary.md) · [TROUBLESHOOTING](./troubleshooting.md) · [Security policy](https://github.com/Gfermoto/BirdLense-Hub/blob/main/SECURITY.md).
