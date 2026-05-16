# Quickstart — BirdLense Hub

[Русский](../ru/quickstart.ru.md)

Fastest paths for the three common jobs: run the hub, develop locally, or verify a deploy.

## 1. Run on one machine

From the repository root — **one command** (Docker, `app/.env`, stack, health checks):

```bash
./install.sh
```

Pre-built image (no local `docker compose build`):

```bash
./install.sh --pull
```

Same via Make: `make install` / `make install-pull`.

What success looks like:

- UI opens at `http://127.0.0.1:8085`
- Script ends after `verify-stack` (health / readiness / status)
- Settings page loads even if cameras / MQTT are not configured yet

## 2. Local development

From the repository root:

```bash
cd app
make local
make verify
make test-web
```

UI dependencies use **Node 22** in `app/ui/`. Full details: [LOCAL_DEV](../contributor/local-dev.md).

### Full CI locally (no GitHub push)

From the **repository root** (Node **≥ 22** required for the UI step):

```bash
make ci-local
```

Adds **`.venv-ci`** / **`.venv-docs`** (gitignored). For Docker image tests + Playwright smoke: `make ci-local-docker`. See [CI_AND_QUALITY](../contributor/ci-and-quality.md).

## 3. Deploy to a server

From the repository root:

```bash
make deploy
BASE_URL=https://YOUR_HOST make verify
```

Success contract after deploy:

- `/api/ui/health` returns `{"status":"ok"}`
- `/api/ui/readiness` returns `"ready": true`
- `/api/ui/status` reports `"web": "ok"`

For the full deploy path, SSH notes, and data-safety details, see [INSTALL](./install.md) and [DEPLOY_SERVER](./deploy-server.md).
