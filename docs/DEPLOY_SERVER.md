# BirdLense Hub server deployment (EN)

Minimal production deployment checklist. Narrative and context: [INSTALL](./INSTALL.md) § *Deploy to server*.

[Русский](./DEPLOY_SERVER.ru.md)

## 1) Prepare

- Ensure SSH access from your local machine to the server.
- Create `scripts/deploy.local.sh` in repo root (copy from `scripts/deploy.local.sh.example`).
- Set at least:
  - `DEPLOY_HOST` — SSH target (host alias from `~/.ssh/config` is fine)
  - `DEPLOY_URL` — hub base URL used **after** deploy for `scripts/verify-stack.sh` (e.g. `http://192.168.1.11:8085` or `https://your.domain/`)
  - optional `DEPLOY_REMOTE_DIR` (default **`/root/BirdLense`** on the server)
  - optional **`DEPLOY_SSH_PORT`** when SSH is not on port 22

Example:

```bash
export DEPLOY_HOST="root@192.168.1.11"
export DEPLOY_URL="http://192.168.1.11:8085"
```

### IP:port first; domain and reverse proxy later

Use the hub at **`http://<host>:<port>`** (default nginx port inside the container is **8080**; on the host map it with **`BIRDLENSE_PORT`**, often **8085**). Set **`DEPLOY_URL`** and, if the browser shows CORS errors, **`CORS_ORIGINS`** in **`app/.env`** on the server to **exactly that URL** (scheme + host + port).

You do **not** need a separate reverse proxy in front of the stack or a DNS name for a working deployment: the container already exposes HTTP on the chosen port. When you later add a **domain + TLS** (and optionally reverse proxy), switch **`DEPLOY_URL`**, **`CORS_ORIGINS`**, and any webhook/public URLs; if TLS terminates at a trusted proxy, set **`TRUSTED_PROXY=1`** — see [CONFIGURATION](./CONFIGURATION.md).

**Operational baseline (VPS by IP, no domain yet):** use the same URL in **`DEPLOY_URL`** (local `deploy.local.sh`) and in server **`app/.env`** as **`CORS_ORIGINS`**, e.g. **`http://185.218.111.196:8085`**. Optional A1 gate before **`make deploy`**: copy server **`app/.env`** to your laptop, then in **`deploy.local.sh`** set **`RUN_VERIFY_PROD_BEFORE_DEPLOY=1`** (and **`VERIFY_PROD_ENV_FILE`** if the copy is not **`app/.env`**) so **`scripts/deploy.sh`** runs **`verify-prod-env`** first — see **`scripts/deploy.local.sh.example`**.

### 1.5 Pre-flight: production environment (VPS / public URL)

For **`BIRDLENSE_ENV=production`**, validate **`app/.env`** on the server (or locally before rsync) against [AGENTS.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/AGENTS.md) production gates — long **`FLASK_SECRET_KEY`** / **`PROCESSOR_SECRET`**, **`BIRDLENSE_STRICT_API_AUTH=1`**, optional MCP token when exposing `/mcp`:

```bash
./scripts/verify-prod-env.sh --env-file app/.env
# or: ENV_FILE=/path/to/.env make verify-prod-env
```

Set **`VERIFY_PROD_ENV=1`** if you need the same checks while `BIRDLENSE_ENV` is not yet `production`. Use **`./scripts/verify-prod-env.sh --require-mcp-token`** when MCP must be gated.

For **browser access from another origin** (UI on a different host/port than the API), set **`CORS_ORIGINS`** / **`CORS_DEFAULT_ORIGINS`** / **`CORS_LOCAL_DEV_ORIGINS`** — see [CONFIGURATION](./CONFIGURATION.md).

## 2) Deploy

From repository root:

```bash
make deploy
```

The command (see `scripts/deploy.sh`):

1. Stops/removes the **`birdlense`** app container (Redis container is left running if present).
2. Runs **`npm ci && npm run build`** in **`app/ui` on your local machine** — requires **Node.js 22** and **npm 10+**.
3. **rsync** repository to the server (excluding `app/data`, `datasets/`, `app/.env`, `user_config.yaml`, `.venv-ci`, `.venv-docs`, `.tools/`, caches, etc.).
4. On the server: **`make stop`**, **`make build`**, **`make start`** under `app/`.
5. Runs **`scripts/verify-stack.sh`** with **`BASE_URL=${DEPLOY_URL}`** (health, readiness, status, cameras when reachable).

## 3) Verify

- Open UI: your **`DEPLOY_URL`** (port **8085** unless you changed **`BIRDLENSE_PORT`**).
- From the **repository root** on your laptop, run the same contract **`make deploy`** uses:

```bash
BASE_URL=http://<server>:8085 make verify
```

(`make verify` wraps **`scripts/verify-stack.sh`**.)


- Or check the endpoints manually:

```bash
curl -sS http://<server>:8085/api/ui/health
curl -sS http://<server>:8085/api/ui/readiness
curl -sS http://<server>:8085/api/ui/status
```

Expected:

```json
{"status":"ok"}
```

For readiness, expect `"ready": true`. For status, expect `"web": "ok"`.

## 4) Data safety

Standard deploy keeps:

- `app/data/` (recordings and DB),
- `app/app_config/user_config.yaml` (user settings).

## 5) Common issues

- **`Password required` on system API**  
  Use an authenticated session (UI login / `verify-password` endpoint).
- **Stale frontend after deploy**  
  Clear browser PWA/Service Worker cache and reload.
- **Port conflict**  
  Verify `BIRDLENSE_PORT` and occupied ports on server.

## 6) Server directory layout

- After `make deploy`, the app root is **`/root/BirdLense`** (or `DEPLOY_REMOTE_DIR` in `deploy.local.sh`). Check `docker inspect birdlense` — the **`/app/data`** mount should point at `…/app/data` under that tree.
- Older docs sometimes used **`/opt/birdlense`**; that is **not** the repo default. A stray `birdlense.db` there may be from an old install—trust `deploy.local.sh`, not an arbitrary path.

## 7) Container logs

- **h264 / rtsp** lines often come from the stream decoder and do not imply the API is broken; the image sets **`OPENCV_*`** to reduce noise.
- **Telegram** startup notify waits briefly after the API is up so SOCKS/proxy can become ready (`notify_app_startup`).

## 8) Direct recording URLs (`/data/recordings/`)

Follow **[PUBLIC_RECORDINGS.md](./PUBLIC_RECORDINGS.md)** — single checklist for public/VPS ( **`BIRDLENSE_HIDE_DIRECT_RECORDINGS`**, strict auth, optional stream lock). This section intentionally stays short to avoid duplicating [SECURITY.md §3](./SECURITY.md).
