# Quickstart — BirdLense Hub

Fastest paths for the three common jobs: run the hub, develop locally, or verify a deploy.

## 1. Run on one machine

From the repository root:

```bash
./install.sh
make verify
```

What success looks like:

- UI opens at `http://127.0.0.1:8085`
- `make verify` passes
- Settings page loads even if cameras / MQTT are not configured yet

If you prefer the published image instead of building locally:

```bash
cd app
make pull
make verify
```

## 2. Local development

From the repository root:

```bash
cd app
make local
make verify
make test-web
```

UI dependencies use **Node 22** in `app/ui/`. Full details: [LOCAL_DEV](./LOCAL_DEV.md).

### Full CI locally (no GitHub push)

From the **repository root** (Node **≥ 22** required for the UI step):

```bash
make ci-local
```

Adds **`.venv-ci`** / **`.venv-docs`** (gitignored). For Docker image tests + Playwright smoke: `make ci-local-docker`. See [CI_AND_QUALITY](./CI_AND_QUALITY.md).

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

For the full deploy path, SSH notes, and data-safety details, see [INSTALL](./INSTALL.md) and [DEPLOY_SERVER](./DEPLOY_SERVER.md).
