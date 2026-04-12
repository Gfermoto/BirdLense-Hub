# BirdLense Hub server deployment (EN)

Minimal production deployment checklist. Narrative and context: [INSTALL](./INSTALL.md) § *Deploy to server*.

[Русский](./DEPLOY_SERVER.ru.md)

## 1) Prepare

- Ensure SSH access from your local machine to the server.
- Create `scripts/deploy.local.sh` in repo root (copy from `scripts/deploy.local.sh.example`).
- Set at least:
  - `DEPLOY_HOST` — SSH target
  - `DEPLOY_URL` — public hub URL
  - optional `DEPLOY_REMOTE_DIR`

Example:

```bash
export DEPLOY_HOST="root@192.168.1.11"
export DEPLOY_URL="http://192.168.1.11:8085"
```

## 2) Deploy

From repository root:

```bash
make deploy
```

The command:

1. Syncs code to server (excluding `app/data`, `site/`, local helper folders).
2. Runs `make stop`, `make build`, `make start` on server.
3. Performs basic post-deploy health checks.

## 3) Verify

- Open UI: `http://<server>:8085`
- Check API health:

```bash
curl -sS http://<server>:8085/api/ui/health
```

Expected:

```json
{"status":"ok"}
```

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

By default nginx serves files under `/data/` without extra HTTP auth. To reduce risk of predictable `video.mp4` URLs, see [SECURITY.md §3](./SECURITY.md) and the network-restriction example: `app/nginx/examples/recordings_allowlist.conf.snippet`.
