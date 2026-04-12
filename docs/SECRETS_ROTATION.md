# Production secrets — rotation runbook

[Русский](./SECRETS_ROTATION.ru.md)

Operational guide for self-hosted BirdLense Hub: where secrets live, how to rotate them safely, verify, and roll back. Complements [SECURITY.md](./SECURITY.md) (risks) and [CONFIGURATION.md](./CONFIGURATION.md) (keys).

---

## Where secrets live

| Location | Used for | Notes |
|----------|----------|--------|
| **`app/.env` on the server** | Container env (`env_file` in Docker Compose) | **Not** overwritten by rsync deploy (excluded). Deploy script **merges** `MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET`, `BIRDLENSE_STRICT_API_AUTH`, `BIRDLENSE_UI_API_KEY` from your **`scripts/deploy.local.sh`** when those variables are set — see [INSTALL.md](./INSTALL.md). |
| **`app/app_config/user_config.yaml`** | Settings UI persistence | Plain text on disk. Prefer env for production secrets ([SECURITY.md](./SECURITY.md) §2). |
| **`scripts/deploy.local.sh`** (gitignored) | Values pushed into server `app/.env` during `make deploy` | Keep canonical copies of deploy-managed keys here so redeploy does not surprise you. |

---

## Inventory (runtime)

### Required in production (`BIRDLENSE_ENV=production`)

| Secret / variable | Role | Rotation impact |
|-------------------|------|-----------------|
| **`FLASK_SECRET_KEY`** | Flask session cookie signing | **All browser sessions invalidated** — operators sign in to Settings again. |
| **`PROCESSOR_SECRET`** | `X-Processor-Token` for processor → web internal API | If mismatch: processor logs **403**, `processor_secret_configured` / activity issues. Must be **one value** in `.env` (same container reads it for both sides). |

### Optional but common

| Secret / variable | Role | Rotation impact |
|-------------------|------|-----------------|
| **`MCP_TOKEN`** | `/mcp` when MCP enabled | Old clients lose access immediately. |
| **`BIRDLENSE_UI_API_KEY`** | Optional: `/api/ui/*` when **`BIRDLENSE_STRICT_API_AUTH=1`** (header `X-Birdlense-Api-Key` or Bearer) | Scripts/automation lose access until updated; browser UI still uses session after `verify-password`. |
| **`BIRDLENSE_STRICT_API_AUTH`** | `1`/`true` — enforce gate (not a secret; production + flag) | If you disable it, anonymous `/api/ui/*` works again per [ACCESS_CONTROL.md](./ACCESS_CONTROL.md). |
| **`MQTT_PASSWORD`** | MQTT client auth | Update broker ACL if needed; restart container. |
| **`HA_TOKEN`** | Home Assistant long-lived token | Weather/feeder integrations break until updated. |
| **`OPENWEATHER_API_KEY`** | Weather widget | Widget errors until key replaced. |
| **`GO2RTC_URL`** | Not a secret; often paired with network changes | Streams break if URL wrong. |

### In Settings / YAML (prefer env when possible)

| Config path | Role |
|-------------|------|
| `general.settings_password` | Settings UI gate |
| `general.telegram_bot_token` | Telegram notifications |
| `mqtt.password` | If not using `MQTT_PASSWORD` env |
| `secrets.openweather_api_key`, `secrets.xeno_canto_api_key`, `secrets.ebird_api_key` | API keys (env vars override or duplicate — see [CONFIGURATION.md](./CONFIGURATION.md)) |
| `homeassistant.token` | If not using `HA_TOKEN` env (legacy: `weather.ha_token`) |
| `mcp.token` | If not using `MCP_TOKEN` env |
| `web_push.vapid_private_key` | Web Push |

Env aliases (examples): `XENO_CANTO_API_KEY` in `.env` — see `app/.env.example`.

---

## Standard rotation procedure

1. **Prepare**
   - Schedule a low-traffic window if rotating `FLASK_SECRET_KEY` (sessions drop).
   - Copy **`app/.env`** and, if you store secrets in YAML, **`app/app_config/user_config.yaml`** to a **private** backup (encrypted storage; never commit).

2. **Apply**
   - Edit server `app/.env` (or Settings UI for YAML-backed fields).
   - If the secret is one of those merged by deploy: update **`scripts/deploy.local.sh`** on the machine that runs `make deploy` **before** the next deploy.
   - Restart the stack: on the server, `cd app && make stop && make start` (or full `make deploy` from dev machine).

3. **Verify**
   - `curl -sf http://127.0.0.1:8085/api/ui/health` (or your public URL) → HTTP 200.
   - UI: open Settings (re-auth if you rotated `FLASK_SECRET_KEY` or `settings_password`).
   - Processor: System → processor logs — no repeating `403` / `PROCESSOR_SECRET` errors after a new detection or heartbeat.
   - Optional: `GET /api/ui/status` — `processor_secret_configured: true` when `PROCESSOR_SECRET` is set.

4. **Rollback**
   - Restore previous `app/.env` (and YAML if changed) from backup.
   - Restart container again.
   - Confirm health and logs as in step 3.

---

## Per-secret notes

### `PROCESSOR_SECRET`

- Generate: `openssl rand -hex 16`.
- **Web and processor share the same `.env`** in the single-container deployment — one key, one restart.
- After rotation, old in-flight nothing to sync; if you use an external processor (unusual), update **both** ends.

### `FLASK_SECRET_KEY`

- Generate: `openssl rand -hex 32` (or similar strong random).
- Expect **full logout** for all Settings sessions.

### `MCP_TOKEN`

- Minimum length enforced by app — use a long random string.
- Update `.env`; if `mcp.token` in YAML is still set, understand precedence ([MCP_SETUP.md](./MCP_SETUP.md)).

### Telegram / MQTT / HA / API keys

- Prefer setting **env** on the server and clearing duplicate fields from YAML to avoid drift.
- After YAML edits, restart container so process env and file watchers align with your deployment.

---

## Deploy script and `.env`

`scripts/deploy.sh` rebuilds server `app/.env` lines for `MCP_TOKEN`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV`, `PROCESSOR_SECRET` from the **local** environment when you run `make deploy`. Keep those exports in **`scripts/deploy.local.sh`** so rotation survives the next deploy.

If `PROCESSOR_SECRET` is **unset** locally, deploy generates a **new** random value and prints it — avoid accidental rotation; always set it explicitly in `deploy.local.sh` for production.

---

## Emergency rotation — incident note template

Copy and fill (store outside the repo):

```text
Date / TZ:
Rotated by:
Reason (leak suspicion / policy / vendor request):

Secrets touched:
  - [ ] FLASK_SECRET_KEY
  - [ ] PROCESSOR_SECRET
  - [ ] MCP_TOKEN
  - [ ] MQTT_*
  - [ ] HA_TOKEN
  - [ ] API keys (list):
  - [ ] settings_password / Telegram / other:

Backup location (encrypted):
Deploy.local.sh updated (Y/N):
Container restarted at:
Health check OK (Y/N):
Processor logs clean (Y/N):
Rollback performed (Y/N):
```

---

## See also

[SECURITY.md](./SECURITY.md) · [CONFIGURATION.md](./CONFIGURATION.md) · [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) · [TESTING.md](./TESTING.md) (processor 403 / `PROCESSOR_SECRET`) · [INSTALL.md](./INSTALL.md) · [RECOVERY_CONFIG.md](./RECOVERY_CONFIG.md)

Issue: [#119](https://github.com/Gfermoto/BirdLense-Hub/issues/119)
