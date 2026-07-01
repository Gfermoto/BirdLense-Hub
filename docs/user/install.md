# Установка на Jetson Orin

## Требования

- Jetson Orin NX 16GB или Orin NANO 8GB
- JetPack 6+ (L4T r36+), NVIDIA drivers
- Docker + NVIDIA Container Toolkit
- ~20GB свободного места (образ + модели)

## Шаг 1: Системные зависимости

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## Шаг 2: Репозиторий

```bash
git clone <url> /home/birdlense/hub
cd /home/birdlense/hub
git checkout dev
```

## Шаг 3: Модели

Создать структуру директорий и разместить ONNX файлы:

```bash
mkdir -p app/processor/models/detection/trapper_ai_v02_2024
mkdir -p app/processor/models/classification/convnext_v2_tiny_eu-common256px
mkdir -p app/processor/models/reid/ornimetrics
mkdir -p app/processor/models/welfare/ornimetrics
```

## Шаг 4: Сборка и запуск

```bash
cp app/.env.example app/.env
# отредактировать .env

cp app/app_config/user_config.orin.example.yaml app/app_config/user_config.yaml
# отредактировать под свою камеру

cd app && make build && make start
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

Image: `ghcr.io/gfermoto/birdlense-hub:latest`. Files: `docker-compose.image.yml`, `.env`, `app_config/`, `data/`.

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

**What it does:** stops/removes container **`birdlense`** (leaves **`birdlense-redis`** if present), runs **local** UI `npm ci && npm run build`, **rsync** with excludes (among others: **`datasets/`**, **`app/data/`**, **`app/.env`**, **`app/app_config/user_config.yaml`**, **`.tools/`**, `node_modules`, ruff/pytest caches), merges secrets into **`app/.env`** on the server (`MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET`, optional **`BIRDLENSE_STRICT_API_AUTH`** / **`BIRDLENSE_UI_API_KEY`** — see [CONFIGURATION.md](./configuration.md)), **`make build && make start`** in `app/` on the server, then **`scripts/verify-stack.sh`** against **`DEPLOY_URL`** (health, readiness, status, cameras when reachable).

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
