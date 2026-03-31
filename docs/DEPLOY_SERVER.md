# BirdLense Hub server deployment (EN)

Minimal production deployment checklist.

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
